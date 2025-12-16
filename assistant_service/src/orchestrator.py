import asyncio
import json
import os
import time

import redis.asyncio as redis
from langchain_core.messages import HumanMessage
from pydantic import ValidationError
from shared_models import (
    AssistantResponseMessage,
    QueueDirection,
    QueueLogger,
    QueueMessage,
    QueueTrigger,
    get_logger,
)

from assistants.base_assistant import BaseAssistant
from assistants.factory import AssistantFactory
from config.settings import Settings
from services.redis_stream import MAX_RETRIES, RedisStreamClient
from services.rest_service import RestServiceClient

RETRY_KEY_PREFIX = "msg_retry:"
RETRY_KEY_TTL = 3600  # 1 hour

logger = get_logger(__name__)


class AssistantOrchestrator:
    def __init__(self, settings: Settings):
        """Initialize the assistant service."""
        # Initialize Redis connection
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=False,
        )

        self.settings = settings
        self.rest_client = RestServiceClient()
        # Pass redis client to factory for distributed caching
        self.factory = AssistantFactory(settings, redis_client=self.redis)
        self.queue_logger = QueueLogger(settings.REST_SERVICE_URL)
        self.input_stream = RedisStreamClient(
            client=self.redis,
            stream=settings.INPUT_QUEUE,
            group=settings.INPUT_STREAM_GROUP,
            consumer=settings.STREAM_CONSUMER,
        )
        self.output_stream = RedisStreamClient(
            client=self.redis,
            stream=settings.OUTPUT_QUEUE,
            group=settings.OUTPUT_STREAM_GROUP,
            consumer=settings.STREAM_CONSUMER,
        )

        logger.info(
            "Assistant service initialized",
        )

    @staticmethod
    def _extract_payload_field(message_fields):
        return message_fields.get("payload") or message_fields.get(b"payload")

    # region agent log
    @staticmethod
    def _dbg_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
        payload = {
            "sessionId": "debug-session",
            "runId": "pre-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        log_paths = [
            "/home/vlad/projects/Assistants/.cursor/debug.log",  # host path
            "/src/debug.log",  # container-mounted path fallback
        ]
        for path in log_paths:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a") as f:
                    f.write(json.dumps(payload) + "\n")
                break
            except Exception:
                continue

    # endregion

    # region retry count management
    async def _get_message_retry_count(self, message_id: str) -> int:
        """Get retry count for a message from Redis."""
        key = f"{RETRY_KEY_PREFIX}{message_id}"
        count = await self.redis.get(key)
        return int(count) if count else 0

    async def _increment_message_retry_count(self, message_id: str) -> int:
        """Increment and return new retry count."""
        key = f"{RETRY_KEY_PREFIX}{message_id}"
        new_count = await self.redis.incr(key)
        await self.redis.expire(key, RETRY_KEY_TTL)
        return new_count

    async def _clear_message_retry_count(self, message_id: str) -> None:
        """Clear retry count after successful processing or DLQ."""
        key = f"{RETRY_KEY_PREFIX}{message_id}"
        await self.redis.delete(key)

    async def _handle_processing_failure(
        self,
        message_id: str,
        raw_payload: bytes | None,
        error: Exception,
        event: QueueMessage | QueueTrigger | None,
    ) -> None:
        """Handle message processing failure - retry or send to DLQ."""
        retry_count = await self._increment_message_retry_count(message_id)

        user_id = getattr(event, "user_id", "unknown") if event else "unknown"
        error_type = type(error).__name__

        if retry_count >= MAX_RETRIES:
            logger.warning(
                "Max retries exceeded, sending to DLQ",
                message_id=message_id,
                retry_count=retry_count,
                error_type=error_type,
                user_id=user_id,
            )

            error_info = {
                "error_type": error_type,
                "error_message": str(error),
                "user_id": str(user_id),
            }

            try:
                await self.input_stream.send_to_dlq(
                    original_message_id=message_id,
                    payload=raw_payload or b"",
                    error_info=error_info,
                    retry_count=retry_count,
                )
                # After DLQ, ACK original message
                await self.input_stream.ack(message_id)
                await self._clear_message_retry_count(message_id)
            except Exception as dlq_exc:
                logger.error(
                    "Failed to send to DLQ",
                    error=str(dlq_exc),
                    message_id=message_id,
                )
        else:
            # Will be retried via xautoclaim
            delay = self.input_stream.get_retry_delay(retry_count - 1)
            logger.info(
                "Message will be retried via xautoclaim",
                message_id=message_id,
                retry_count=retry_count,
                next_retry_delay_seconds=delay,
                error_type=error_type,
                user_id=user_id,
            )
            # Don't ACK - message stays in pending list for xautoclaim

    # endregion

    async def _dispatch_event(self, event: QueueMessage | QueueTrigger) -> dict | None:
        """Handle incoming events and dispatch to secretary."""
        user_id = None
        start_time = time.perf_counter()
        get_secretary_start_time = None
        process_message_start_time = None
        log_extra = {}
        lc_message: HumanMessage

        try:
            # Extract user_id from the event
            user_id = event.user_id
            # Normalize to seconds to avoid extra tokens
            timestamp_iso = event.timestamp.replace(microsecond=0).isoformat()

            # Prepare common log info
            log_extra = {
                "user_id": user_id,
                "timestamp": timestamp_iso,
                "message_class": type(event).__name__,
            }

            # Create Langchain message and extract source based on event type
            if isinstance(event, QueueMessage):
                log_extra["event_type"] = "user_message"
                source = (
                    event.metadata.get("source", "unknown")
                    if event.metadata
                    else "unknown"
                )
                log_extra["source"] = source

                # Add source and timestamp to metadata for Langchain message
                lc_metadata = event.metadata or {}
                lc_metadata["source"] = source
                lc_metadata["timestamp"] = timestamp_iso

                human_content = f"(Sent at UTC: {timestamp_iso}) {event.content}"
                lc_message = HumanMessage(
                    content=human_content,
                    metadata=lc_metadata,
                )
                text_for_response = event.content  # For response payload

            elif isinstance(event, QueueTrigger):
                trigger_type_val = event.trigger_type.value
                source_val = event.source.value
                log_extra["event_type"] = trigger_type_val
                log_extra["source"] = source_val
                log_extra["payload_preview"] = str(event.payload)[:100]

                # Prepare metadata for Langchain message
                lc_metadata = {
                    "source": source_val,
                    "timestamp": timestamp_iso,
                    "is_trigger": True,  # Flag to indicate system trigger
                }

                # Content for HumanMessage indicating a system trigger
                try:
                    payload_json = json.dumps(event.payload)
                except TypeError:
                    payload_json = str(event.payload)  # Fallback

                human_content = (
                    "System Trigger Activated:\n"
                    f"Timestamp UTC: {timestamp_iso}\n"
                    f"Type: {trigger_type_val}\n"
                    f"Source: {source_val}\n"
                    f"Payload: {payload_json}"
                )

                # Create HumanMessage instead of ToolMessage
                lc_message = HumanMessage(
                    content=human_content,
                    metadata=lc_metadata,
                )
                text_for_response = (
                    f"Trigger: {trigger_type_val}"  # For response payload
                )

            else:
                # Should not happen with Union type hint, but defensive check
                raise TypeError(f"Unsupported event type: {type(event)}")

            logger.info(f"Processing {log_extra['message_class']}", extra=log_extra)

            # Получение секретаря для пользователя
            get_secretary_start_time = time.perf_counter()
            secretary: BaseAssistant = await self.factory.get_user_secretary(user_id)
            get_secretary_duration = time.perf_counter() - get_secretary_start_time
            log_extra["get_secretary_duration_ms"] = round(
                get_secretary_duration * 1000
            )

            if not secretary:
                logger.error(
                    "Failed to get secretary instance from factory", extra=log_extra
                )
                raise ValueError(f"Could not retrieve secretary for user {user_id}")

            logger.info(
                "Retrieved secretary via factory",
                assistant_name=secretary.name,
                extra=log_extra,
            )

            # Вызов process_message с сообщением, user_id и логами
            process_message_start_time = time.perf_counter()
            ai_response = await secretary.process_message(
                message=lc_message, user_id=str(user_id), log_extra=log_extra
            )
            process_message_duration = time.perf_counter() - process_message_start_time
            log_extra["process_message_duration_ms"] = round(
                process_message_duration * 1000
            )

            logger.info(
                "Secretary response received",
                response_preview=str(ai_response)[:100]
                if ai_response
                else "No response",
                extra=log_extra,
            )

            # Prepare result payload
            result = {
                "user_id": user_id,
                "text": text_for_response,  # Use appropriate text representation
                "response": ai_response,
                "status": "success",
                "source": log_extra["source"],  # Original source (telegram or cron etc)
                "type": "assistant",  # Or derive from response?
                "metadata": lc_message.metadata,  # Pass the metadata we added
            }
            total_duration = time.perf_counter() - start_time
            log_extra["total_processing_duration_ms"] = round(total_duration * 1000)
            logger.info(
                f"{log_extra['message_class']} processing completed successfully",
                extra=log_extra,
            )
            return result

        except (
            ValueError,
            TypeError,
            KeyError,
            ValidationError,
        ) as e:  # Added ValidationError
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "message_class": type(event).__name__
                if "event" in locals()
                else "unknown",
                # Attempt to get specific attributes if possible
                "event_type": log_extra.get("event_type", "unknown"),
                "source": log_extra.get("source", "unknown"),
            }
            logger.warning(
                "Invalid event data/structure",
                error_type=type(e).__name__,
                error=str(e),
                **log_extra,
            )
            # Try to extract original text/payload for error response metadata
            error_metadata = {}
            if isinstance(event, QueueMessage):
                error_metadata = event.metadata or {}
            elif isinstance(event, QueueTrigger):
                error_metadata = event.payload or {}

            return {
                "user_id": log_extra["user_id"],
                "text": getattr(event, "content", None)
                if isinstance(event, QueueMessage)
                else f"Trigger: {log_extra['event_type']}",
                "status": "error",
                "response": (
                    "Event processing failed due to an internal error: "
                    f"{type(e).__name__}"
                ),
                "error": str(e),
                "source": log_extra["source"],
                "type": "error",
                "metadata": error_metadata,
            }
        except Exception as e:
            total_duration = time.perf_counter() - start_time
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "message_class": type(event).__name__
                if "event" in locals()
                else "unknown",
                # Attempt to get specific attributes if possible
                "event_type": log_extra.get("event_type", "unknown"),
                "source": log_extra.get("source", "unknown"),
                "total_processing_duration_ms": round(total_duration * 1000),
            }
            logger.exception(
                "Event processing failed unexpectedly",
                error=str(e),
                exc_info=True,
                **log_extra,
            )
            # Try to extract original text/payload for error response metadata
            error_metadata = {}
            if isinstance(event, QueueMessage):
                error_metadata = event.metadata or {}
            elif isinstance(event, QueueTrigger):
                error_metadata = event.payload or {}

            return {
                "user_id": log_extra["user_id"],
                "text": getattr(event, "content", None)
                if isinstance(event, QueueMessage)
                else f"Trigger: {log_extra['event_type']}",
                "status": "error",
                "response": (
                    "Event processing failed due to an internal error: "
                    f"{type(e).__name__}"
                ),
                "error": str(e),
                "source": log_extra["source"],
                "type": "error",
                "metadata": error_metadata,
            }

    async def listen_for_messages(self):
        """Listen for messages/triggers from Redis and dispatch."""
        await self.input_stream.ensure_group()
        await self.output_stream.ensure_group()
        logger.info(
            "Starting message listener",
            input_queue=self.settings.INPUT_QUEUE,
            output_queue=self.settings.OUTPUT_QUEUE,
        )
        while True:
            raw_message_bytes = None
            response_payload = None
            event_object: QueueMessage | QueueTrigger | None = None
            stream_message_id: str | None = None
            should_ack: bool = False
            processing_error: Exception | None = None

            try:
                stream_entry = await self.input_stream.read()
                if not stream_entry:
                    continue

                stream_message_id, message_fields = stream_entry
                # region agent log
                self._dbg_log(
                    "A",
                    "orchestrator.listen_for_messages:after_read",
                    "Received stream entry",
                    {
                        "message_id": stream_message_id,
                        "field_keys": list(message_fields.keys()),
                        "input_queue": self.settings.INPUT_QUEUE,
                    },
                )
                # endregion
                raw_message_bytes = self._extract_payload_field(message_fields)
                if raw_message_bytes is None:
                    logger.error(
                        "Stream message missing payload",
                        extra={
                            "stream": self.settings.INPUT_QUEUE,
                            "message_id": stream_message_id,
                        },
                    )
                    # Invalid message structure - ACK and skip (no point retrying)
                    await self.input_stream.ack(stream_message_id)
                    should_ack = True
                    continue

                raw_message_json = (
                    raw_message_bytes.decode("utf-8")
                    if isinstance(raw_message_bytes, (bytes, bytearray))
                    else str(raw_message_bytes)
                )

                message_dict = json.loads(raw_message_json)
                logger.debug(
                    "Successfully parsed JSON",
                    extra={"keys": list(message_dict.keys())},
                )
                # region agent log
                self._dbg_log(
                    "B",
                    "orchestrator.listen_for_messages:after_json",
                    "Parsed JSON",
                    {
                        "keys": list(message_dict.keys()),
                        "has_trigger_type": "trigger_type" in message_dict,
                        "has_content": "content" in message_dict,
                    },
                )
                # endregion

                # Reset event_object before attempting QueueMessage parse
                event_object = None
                if "trigger_type" in message_dict:
                    try:
                        event_object = QueueTrigger(**message_dict)
                        logger.info(
                            "QueueTrigger received for user "
                            f"{event_object.user_id}, type: "
                            f"{event_object.trigger_type.value}"
                        )
                    except ValidationError as trigger_exc:
                        logger.error(
                            f"Failed to parse as QueueTrigger: {trigger_exc}",
                            raw_message=raw_message_json,
                        )
                        event_object = None  # Reset on parse failure
                    except Exception as exc:  # Catch other potential errors
                        logger.error(
                            f"Unexpected error parsing as QueueTrigger: {exc}",
                            raw_message=raw_message_json,
                            exc_info=True,
                        )
                        event_object = None
                elif "content" in message_dict:  # If not a trigger, try as QueueMessage
                    try:
                        event_object = QueueMessage(**message_dict)
                        logger.info(
                            f"QueueMessage received for user {event_object.user_id}"
                        )
                    except ValidationError as msg_exc:
                        logger.error(
                            f"Failed to parse as QueueMessage: {msg_exc}",
                            raw_message=raw_message_json,
                        )
                        event_object = None  # Reset on parse failure
                    except Exception as exc:  # Catch other potential errors
                        logger.error(
                            f"Unexpected error parsing as QueueMessage: {exc}",
                            raw_message=raw_message_json,
                            exc_info=True,
                        )
                        event_object = None
                else:
                    # Handle case where it's neither a valid trigger nor a message
                    logger.error(
                        "Message is neither QueueTrigger nor QueueMessage.",
                        keys=list(message_dict.keys()),
                        raw_message=raw_message_json,
                    )
                    event_object = None

                # Dispatch if parsing succeeded
                if event_object:
                    # Now event_object can be either QueueMessage or QueueTrigger
                    # Assign the result directly to response_payload
                    # region agent log
                    self._dbg_log(
                        "C",
                        "orchestrator.listen_for_messages:before_dispatch",
                        "Dispatching event",
                        {
                            "event_class": type(event_object).__name__,
                            "user_id": getattr(event_object, "user_id", None),
                            "source": getattr(event_object, "source", None).value
                            if hasattr(event_object, "source")
                            else None,
                        },
                    )
                    # endregion

                    # Log inbound message to REST API
                    try:
                        user_id_int = (
                            int(str(event_object.user_id).split("-")[0])
                            if event_object.user_id
                            else None
                        )
                        msg_type = (
                            "trigger"
                            if isinstance(event_object, QueueTrigger)
                            else "human"
                        )
                        source_val = (
                            event_object.source.value
                            if hasattr(event_object, "source") and event_object.source
                            else (
                                event_object.metadata.get("source")
                                if hasattr(event_object, "metadata")
                                and event_object.metadata
                                else "unknown"
                            )
                        )
                        await self.queue_logger.log_message(
                            queue_name="to_secretary",
                            direction=QueueDirection.INBOUND,
                            message_type=msg_type,
                            payload=message_dict,
                            user_id=user_id_int,
                            source=source_val,
                        )
                    except Exception as log_err:
                        logger.warning(
                            "Failed to log inbound queue message",
                            error=str(log_err),
                        )

                    response_payload = await self._dispatch_event(event_object)

                    # Check if processing was successful
                    if response_payload and response_payload.get("status") == "success":
                        should_ack = True
                        await self._clear_message_retry_count(stream_message_id)
                    elif response_payload:
                        # Processing returned error - will be handled in finally
                        processing_error = Exception(
                            response_payload.get("error", "Unknown processing error")
                        )
                else:
                    # Parsing failed or structure was invalid - ACK (no point retrying)
                    logger.error(
                        "Failed to parse incoming message or trigger.",
                        raw_message=raw_message_json,
                    )
                    # Create generic error response payload
                    response_payload = {
                        "user_id": message_dict.get("user_id", "unknown"),
                        "status": "error",
                        "response": "Failed to parse incoming data.",
                        "error": "Invalid data structure or parsing error.",
                        "source": message_dict.get(
                            "source", "unknown"
                        ),  # Try to get source if available
                        "type": "error",
                        "metadata": {},
                    }
                    # Parse errors are not retryable - ACK immediately
                    should_ack = True

                # Send response if any
                if response_payload:
                    # region agent log
                    self._dbg_log(
                        "D",
                        "orchestrator.listen_for_messages:before_output_add",
                        "Enqueuing response",
                        {
                            "message_id": stream_message_id,
                            "user_id": response_payload.get("user_id"),
                            "output_queue": self.settings.OUTPUT_QUEUE,
                        },
                    )
                    # endregion
                    try:
                        # Use AssistantResponseMessage for structuring the response
                        response_message = AssistantResponseMessage(
                            user_id=response_payload.get("user_id", "unknown"),
                            status=response_payload.get("status", "error"),
                            source=response_payload.get(
                                "source", "system"
                            ),  # Source of the response
                            response=response_payload.get("response")
                            if response_payload.get("status") == "success"
                            else None,
                            error=response_payload.get("error")
                            if response_payload.get("status") == "error"
                            else None,
                        )
                        response_json = response_message.model_dump_json()
                        logger.debug(
                            "Sending response to output queue",
                            queue=self.settings.OUTPUT_QUEUE,
                            payload_preview=response_json[:200],
                        )
                        await self.output_stream.add(response_json)
                        logger.info(
                            "Response sent to output queue",
                            user_id=response_payload.get("user_id"),
                        )

                        # Log outbound message to REST API
                        try:
                            user_id_out = response_payload.get("user_id")
                            user_id_int_out = (
                                int(str(user_id_out).split("-")[0])
                                if user_id_out and user_id_out != "unknown"
                                else None
                            )
                            await self.queue_logger.log_message(
                                queue_name="to_telegram",
                                direction=QueueDirection.OUTBOUND,
                                message_type="response",
                                payload=response_payload,
                                user_id=user_id_int_out,
                                source="assistant",
                            )
                        except Exception as log_err:
                            logger.warning(
                                "Failed to log outbound queue message",
                                error=str(log_err),
                            )
                    except ValidationError as resp_exc:
                        logger.error(
                            f"Failed to validate response payload: {resp_exc}",
                            response_payload=response_payload,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to send response to Redis",
                            error=str(e),
                            exc_info=True,
                            user_id=response_payload.get("user_id", "unknown"),
                        )

            except ConnectionError as e:
                logger.error(f"Redis connection error: {e}")
                # Connection errors - don't set processing_error, will retry naturally
                await asyncio.sleep(5)
                continue
            except Exception as e:
                processing_error = e
                logger.error(
                    f"Error in message listener loop: {e}",
                    exc_info=True,
                    raw_message=raw_message_bytes.decode("utf-8", errors="ignore")
                    if raw_message_bytes
                    else "N/A",
                )
                # Avoid tight loop on persistent errors
                await asyncio.sleep(1)
            finally:
                if stream_message_id:
                    if should_ack:
                        # Success or non-retryable error - ACK the message
                        try:
                            await self.input_stream.ack(stream_message_id)
                        except Exception as ack_exc:
                            logger.error(
                                "Failed to ACK message",
                                extra={
                                    "stream": self.settings.INPUT_QUEUE,
                                    "message_id": stream_message_id,
                                    "error": str(ack_exc),
                                },
                            )
                    elif processing_error:
                        # Failure - handle retry or DLQ
                        await self._handle_processing_failure(
                            message_id=stream_message_id,
                            raw_payload=raw_message_bytes,
                            error=processing_error,
                            event=event_object,
                        )

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()
        logger.info("Redis connection closed.")
