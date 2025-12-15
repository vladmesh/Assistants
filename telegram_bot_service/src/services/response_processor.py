import asyncio
import json

import structlog
from pydantic import ValidationError
from redis import asyncio as aioredis
from redis.exceptions import ResponseError
from shared_models import QueueDirection, QueueLogger
from shared_models.queue import AssistantResponseMessage

from clients.rest import RestClient
from clients.telegram import TelegramClient
from config.settings import settings

logger = structlog.get_logger()
queue_logger = QueueLogger(settings.rest_service_url)


async def handle_assistant_responses(
    telegram: TelegramClient, redis: aioredis.Redis
) -> None:
    """
    Handle responses from assistant.

    Args:
        telegram: Telegram client instance
        redis: Redis client instance
    """
    logger.info("Started assistant response handler")

    await _ensure_output_group(redis)

    async with RestClient() as rest:
        while True:
            try:
                message_id, data = await _read_next_response(redis)
                if not message_id:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    response_message = AssistantResponseMessage.model_validate_json(
                        data
                    )
                    logger.debug(
                        "Successfully validated AssistantResponseMessage",
                        user_id=response_message.user_id,
                    )

                    # Log to REST API for observability
                    try:
                        await queue_logger.log_message(
                            queue_name="to_telegram",
                            direction=QueueDirection.OUTBOUND,
                            message_type="response",
                            payload=response_message.model_dump(),
                            user_id=int(str(response_message.user_id).split("-")[0])
                            if response_message.user_id
                            else None,
                            source="assistant",
                        )
                    except Exception as log_err:
                        logger.warning(
                            "Failed to log queue message to REST API",
                            error=str(log_err),
                        )

                except ValidationError as e:
                    logger.error(
                        "Failed to validate assistant response from stream",
                        raw_data=data.decode("utf-8", errors="ignore"),
                        errors=e.errors(),
                        exc_info=True,
                    )
                    await _ack_response(redis, message_id)
                    continue

                # Get user data from REST service using validated user_id
                user_id = response_message.user_id
                user = await rest.get_user_by_id(user_id)
                if not user:
                    logger.error("User not found", user_id=user_id)
                    await _ack_response(redis, message_id)
                    continue

                chat_id = user.telegram_id
                if not chat_id:
                    logger.error("No telegram_id in user data object", user_id=user_id)
                    await _ack_response(redis, message_id)
                    continue

                if response_message.status == "error":
                    error_message = (
                        response_message.error or "Произошла неизвестная ошибка"
                    )
                    logger.error(
                        "Error received in assistant response",
                        error=error_message,
                        user_id=user_id,
                        source=response_message.source,
                    )
                    await telegram.send_message(
                        chat_id=chat_id,
                        text=f"Извините, произошла ошибка: {error_message}",
                    )
                else:
                    response_text = response_message.response
                    if response_text:
                        await telegram.send_message(
                            chat_id=chat_id,
                            text=response_text,
                        )
                        logger.info(
                            "Sent successful response to user",
                            user_id=user_id,
                            message_preview=response_text[:100],
                            source=response_message.source,
                        )
                    else:
                        logger.warning(
                            "Empty successful response from assistant",
                            user_id=user_id,
                            source=response_message.source,
                        )
                await _ack_response(redis, message_id)

            except json.JSONDecodeError as e:  # Should be caught by ValidationError now
                logger.error(
                    "Invalid JSON in response (should be caught by validation)",
                    error=str(e),
                )
            except KeyError as e:  # Should be caught by ValidationError now
                logger.error(
                    "Missing required field in response "
                    "(should be caught by validation)",
                    error=str(e),
                )
            except Exception as e:
                logger.error("Error handling assistant response", error=str(e))

            # Small delay to prevent tight loop
            await asyncio.sleep(0.1)


async def _ensure_output_group(redis: aioredis.Redis) -> None:
    try:
        await redis.xgroup_create(
            name=settings.assistant_output_queue,
            groupname=settings.output_stream_group,
            id="0",
            mkstream=True,
        )
        logger.info(
            "Created consumer group for assistant responses",
            stream=settings.assistant_output_queue,
            group=settings.output_stream_group,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def _read_next_response(
    redis: aioredis.Redis,
) -> tuple[str | None, bytes | None]:
    entries = await redis.xreadgroup(
        groupname=settings.output_stream_group,
        consumername=settings.stream_consumer,
        streams={settings.assistant_output_queue: ">"},
        count=1,
        block=1000,
    )
    if entries:
        _, messages = entries[0]
        if messages:
            message_id, fields = messages[0]
            payload = fields.get("payload") or fields.get(b"payload")
            if payload:
                return message_id, payload if isinstance(payload, bytes) else str(
                    payload
                ).encode()

    # Reclaim stale pending
    _start, claimed, _ = await redis.xautoclaim(
        name=settings.assistant_output_queue,
        groupname=settings.output_stream_group,
        consumername=settings.stream_consumer,
        min_idle_time=60_000,
        start_id="0-0",
        count=1,
    )
    if claimed:
        message_id, fields = claimed[0]
        payload = fields.get("payload")
        if payload:
            return message_id, payload if isinstance(payload, bytes) else str(
                payload
            ).encode()
    return None, None


async def _ack_response(redis: aioredis.Redis, message_id: str) -> None:
    try:
        await redis.xack(
            settings.assistant_output_queue,
            settings.output_stream_group,
            message_id,
        )
    except Exception as exc:
        logger.error(
            "Failed to ACK response message",
            error=str(exc),
            message_id=message_id,
            stream=settings.assistant_output_queue,
        )
