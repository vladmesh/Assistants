import json
import time
from typing import Optional

import redis.asyncio as redis
from assistants.base_assistant import BaseAssistant
from assistants.factory import AssistantFactory
from config.logger import get_logger
from config.settings import Settings
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import ValidationError
from services.rest_service import RestServiceClient

from shared_models import (
    AssistantResponseMessage,
    QueueMessage,
    QueueMessageType,
    QueueTrigger,
)

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
        self.factory = AssistantFactory(settings)
        # Remove the orchestrator-level cache
        # self.secretaries: Dict[int, BaseAssistant] = {}

        logger.info(
            "Assistant service initialized",
        )

    def _create_message(
        self, queue_message: QueueMessage
    ) -> HumanMessage | ToolMessage:
        """Create appropriate message type from queue message."""
        logger.info(
            "Creating message from queue message",
            type=queue_message.type,
            source=queue_message.source,
            user_id=queue_message.user_id,
            content_message=queue_message.content.message,
            content_metadata=queue_message.content.metadata,
            timestamp=queue_message.timestamp,
        )

        if queue_message.type == QueueMessageType.HUMAN:
            message = HumanMessage(
                content=queue_message.content.message,
                metadata=queue_message.content.metadata,
            )
            logger.info("Created human message", message=str(message))
            return message
        elif queue_message.type == QueueMessageType.TOOL:
            metadata = queue_message.content.metadata or {}
            tool_name = metadata.get("tool_name", "unknown")
            message = ToolMessage(
                content=queue_message.content.message,
                tool_call_id=str(queue_message.timestamp.timestamp()),
                tool_name=tool_name,
                metadata=metadata,
            )
            logger.info("Created tool message", message=str(message))
            return message
        else:
            logger.error(
                "Unsupported message type encountered in _create_message",
                type=queue_message.type,
            )
            raise ValueError(f"Unsupported message type: {queue_message.type}")

    async def process_message(self, queue_message: QueueMessage) -> Optional[dict]:
        """Process an incoming standard QueueMessage."""
        user_id = None
        start_time = time.perf_counter()
        get_secretary_start_time = None
        process_message_start_time = None
        log_extra = {}
        try:
            user_id = queue_message.user_id
            text = (
                queue_message.content.message
                if hasattr(queue_message.content, "message")
                else "N/A"
            )

            log_extra = {
                "user_id": user_id,
                "source": queue_message.source.value
                if queue_message.source
                else "unknown",
                "type": queue_message.type.value if queue_message.type else "unknown",
                "timestamp": queue_message.timestamp.isoformat()
                if queue_message.timestamp
                else "unknown",
                "message_class": "QueueMessage",
            }
            logger.info("Processing QueueMessage", extra=log_extra)

            logger.debug("Getting secretary from factory", extra=log_extra)
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

            message = self._create_message(queue_message)
            logger.debug(
                "Langchain message created",
                message_type=type(message).__name__,
                extra=log_extra,
            )

            logger.debug(
                "Invoking secretary.process_message for QueueMessage", extra=log_extra
            )
            process_message_start_time = time.perf_counter()
            response = await secretary.process_message(
                message=message, user_id=str(user_id), triggered_event=None
            )
            process_message_duration = time.perf_counter() - process_message_start_time
            log_extra["process_message_duration_ms"] = round(
                process_message_duration * 1000
            )
            logger.info(
                "Secretary response received",
                response_preview=str(response)[:100],
                extra=log_extra,
            )

            result = {
                "user_id": user_id,
                "text": text,
                "response": response,
                "status": "success",
                "source": log_extra["source"],
                "type": "assistant",
                "metadata": queue_message.content.metadata or {},
            }
            total_duration = time.perf_counter() - start_time
            log_extra["total_processing_duration_ms"] = round(total_duration * 1000)
            logger.info(
                "QueueMessage processing completed successfully", extra=log_extra
            )
            return result

        except (ValueError, TypeError, KeyError) as e:
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "source": getattr(queue_message, "source", "unknown").value
                if hasattr(getattr(queue_message, "source", None), "value")
                else "unknown",
                "type": getattr(queue_message, "type", "unknown").value
                if hasattr(getattr(queue_message, "type", None), "value")
                else "unknown",
                "message_class": "QueueMessage",
            }
            logger.warning(
                f"Error processing QueueMessage due to invalid data/structure: {type(e).__name__}",
                error=str(e),
                **log_extra,
            )
            return {
                "user_id": log_extra["user_id"],
                "text": getattr(
                    getattr(queue_message, "content", None), "message", "unknown"
                ),
                "status": "error",
                "response": f"Message processing failed due to an internal error: {type(e).__name__}",
                "error": str(e),
                "source": log_extra["source"],
                "type": "error",
                "metadata": getattr(
                    getattr(queue_message, "content", None), "metadata", {}
                )
                or {},
            }
        except Exception as e:
            total_duration = time.perf_counter() - start_time
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "source": getattr(queue_message, "source", "unknown").value
                if hasattr(getattr(queue_message, "source", None), "value")
                else "unknown",
                "type": getattr(queue_message, "type", "unknown").value
                if hasattr(getattr(queue_message, "type", None), "value")
                else "unknown",
                "total_processing_duration_ms": round(total_duration * 1000),
                "message_class": "QueueMessage",
            }
            logger.exception(
                "QueueMessage processing failed unexpectedly",
                error=str(e),
                exc_info=True,
                **log_extra,
            )
            return {
                "user_id": log_extra["user_id"],
                "text": getattr(
                    getattr(queue_message, "content", None), "message", "unknown"
                ),
                "status": "error",
                "response": f"Message processing failed due to an internal error: {type(e).__name__}",
                "error": str(e),
                "source": log_extra["source"],
                "type": "error",
                "metadata": getattr(
                    getattr(queue_message, "content", None), "metadata", {}
                )
                or {},
            }

    async def handle_trigger(self, trigger: QueueTrigger) -> Optional[dict]:
        """Handles incoming system trigger events (QueueTrigger)."""
        user_id = None
        start_time = time.perf_counter()
        get_secretary_start_time = None
        process_message_start_time = None
        log_extra = {}
        try:
            user_id = trigger.user_id
            trigger_type_val = trigger.trigger_type.value
            source_val = trigger.source.value

            log_extra = {
                "user_id": user_id,
                "trigger_type": trigger_type_val,
                "source": source_val,
                "payload_preview": str(trigger.payload)[:100],
                "timestamp": trigger.timestamp.isoformat(),
                "message_class": "QueueTrigger",
            }
            logger.info("Handling QueueTrigger event", extra=log_extra)

            logger.debug("Getting secretary for trigger", extra=log_extra)
            get_secretary_start_time = time.perf_counter()
            secretary: BaseAssistant = await self.factory.get_user_secretary(user_id)
            get_secretary_duration = time.perf_counter() - get_secretary_start_time
            log_extra["get_secretary_duration_ms"] = round(
                get_secretary_duration * 1000
            )

            if not secretary:
                logger.error(
                    "Secretary not found for user via factory", extra=log_extra
                )
                return {
                    "user_id": user_id,
                    "status": "error",
                    "response": "Failed to process trigger: Secretary not found for user.",
                    "error": f"Secretary not found for user_id {user_id}",
                    "source": trigger_type_val,
                    "type": "error",
                    "metadata": trigger.payload,
                }

            logger.info(
                "Retrieved secretary instance via factory for trigger",
                assistant_name=secretary.name,
                extra=log_extra,
            )

            trigger_event_data = trigger.model_dump(mode="json")
            logger.debug(
                "Prepared trigger event data for secretary",
                data=trigger_event_data,
                extra=log_extra,
            )

            logger.debug(
                "Invoking secretary.process_message for trigger", extra=log_extra
            )
            process_message_start_time = time.perf_counter()
            response_text = await secretary.process_message(
                message=None,
                user_id=str(user_id),
                triggered_event=trigger_event_data,
            )
            process_message_duration = time.perf_counter() - process_message_start_time
            log_extra["process_message_duration_ms"] = round(
                process_message_duration * 1000
            )

            logger.info(
                "Secretary processed trigger event",
                response_preview=str(response_text)[:100],
                extra=log_extra,
            )

            response_payload = {
                "user_id": user_id,
                "response": response_text,
                "status": "success",
                "source": trigger_type_val,
                "type": "assistant",
                "metadata": trigger.payload,
            }
            logger.debug(
                "Trigger response payload prepared",
                payload=response_payload,
                extra=log_extra,
            )

            total_duration = time.perf_counter() - start_time
            log_extra["total_processing_duration_ms"] = round(total_duration * 1000)
            logger.info(
                "QueueTrigger processing completed successfully", extra=log_extra
            )
            return response_payload

        except (ValueError, TypeError, KeyError) as e:
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "trigger_type": getattr(trigger, "trigger_type", "unknown").value
                if hasattr(getattr(trigger, "trigger_type", None), "value")
                else "unknown",
                "source": getattr(trigger, "source", "unknown").value
                if hasattr(getattr(trigger, "source", None), "value")
                else "unknown",
                "message_class": "QueueTrigger",
            }
            logger.warning(
                f"Error handling QueueTrigger due to invalid data: {type(e).__name__}",
                error=str(e),
                **log_extra,
            )
            return {
                "user_id": log_extra["user_id"],
                "status": "error",
                "response": f"Failed to process trigger: {type(e).__name__}",
                "error": str(e),
                "source": log_extra["trigger_type"],
                "type": "error",
                "metadata": getattr(trigger, "payload", {}) or {},
            }

        except Exception as e:
            total_duration = time.perf_counter() - start_time
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "trigger_type": getattr(trigger, "trigger_type", "unknown").value
                if hasattr(getattr(trigger, "trigger_type", None), "value")
                else "unknown",
                "source": getattr(trigger, "source", "unknown").value
                if hasattr(getattr(trigger, "source", None), "value")
                else "unknown",
                "total_processing_duration_ms": round(total_duration * 1000),
                "message_class": "QueueTrigger",
            }
            logger.exception(
                "Unexpected error handling QueueTrigger",
                error=str(e),
                exc_info=True,
                **log_extra,
            )
            return {
                "user_id": log_extra["user_id"],
                "status": "error",
                "response": f"Internal error processing trigger: {type(e).__name__}",
                "error": str(e),
                "source": log_extra["trigger_type"],
                "type": "error",
                "metadata": getattr(trigger, "payload", {}) or {},
            }

    async def listen_for_messages(self, max_messages: int | None = None):
        """Listen for incoming messages/triggers from Redis queue and dispatch processing."""
        logger.info(
            "Starting message listener",
            input_queue=self.settings.INPUT_QUEUE,
            output_queue=self.settings.OUTPUT_QUEUE,
            max_messages=max_messages if max_messages else "unlimited",
        )
        processed_count = 0
        while max_messages is None or processed_count < max_messages:
            raw_message_bytes = None
            try:
                message_data = await self.redis.blpop(
                    [self.settings.INPUT_QUEUE], timeout=5
                )

                if not message_data:
                    continue

                _, raw_message_bytes = message_data
                raw_message_json = raw_message_bytes.decode("utf-8")
                logger.debug(
                    "Raw message received (JSON string)",
                    message_json_preview=raw_message_json[:200],
                )

                message_dict = json.loads(raw_message_json)
                logger.debug(
                    "Successfully parsed JSON",
                    extra={"keys": list(message_dict.keys())},
                )

                response_payload = None

                if "trigger_type" in message_dict:
                    try:
                        trigger = QueueTrigger(**message_dict)
                        user_id = trigger.user_id
                        logger.info(
                            f"QueueTrigger received for user {user_id} (type: {trigger.trigger_type.value})",
                        )
                        logger.debug("Calling handle_trigger")
                        response_payload = await self.handle_trigger(trigger)
                        logger.debug(
                            "handle_trigger finished",
                            has_payload=response_payload is not None,
                        )
                    except Exception as parse_exc:
                        logger.error(
                            f"Failed to parse QueueTrigger: {parse_exc}",
                            raw_message=raw_message_json,
                            exc_info=True,
                        )
                        response_payload = {
                            "user_id": message_dict.get("user_id", "unknown"),
                            "status": "error",
                            "response": f"Failed to parse incoming trigger: {parse_exc}",
                            "error": str(parse_exc),
                            "source": message_dict.get("source", "unknown"),
                            "type": "error",
                            "metadata": message_dict.get("payload", {}),
                        }

                elif "type" in message_dict:
                    try:
                        queue_message = QueueMessage(**message_dict)
                        user_id = queue_message.user_id
                        logger.info(
                            f"Standard QueueMessage received for user {user_id} (type: {queue_message.type.value})",
                        )
                        logger.debug("Calling process_message")
                        response_payload = await self.process_message(queue_message)
                        logger.debug(
                            "process_message finished",
                            has_payload=response_payload is not None,
                        )
                    except Exception as parse_exc:
                        logger.error(
                            f"Failed to parse QueueMessage: {parse_exc}",
                            raw_message=raw_message_json,
                            exc_info=True,
                        )
                        response_payload = {
                            "user_id": message_dict.get("user_id", "unknown"),
                            "status": "error",
                            "response": f"Failed to parse incoming message: {parse_exc}",
                            "error": str(parse_exc),
                            "source": message_dict.get("source", "unknown"),
                            "type": "error",
                            "metadata": message_dict.get("content", {}).get(
                                "metadata", {}
                            ),
                        }
                else:
                    logger.error(
                        f"Received message with unknown structure (missing 'type' or 'trigger_type')",
                        raw_message=raw_message_json,
                    )
                    response_payload = {
                        "user_id": message_dict.get("user_id", "unknown"),
                        "status": "error",
                        "response": f"Unknown message structure received.",
                        "error": "Missing 'type' or 'trigger_type' key",
                        "source": message_dict.get("source", "unknown"),
                        "type": "error",
                        "metadata": message_dict.get("payload")
                        or message_dict.get("content", {}).get("metadata", {}),
                    }

                if response_payload:
                    try:
                        logger.debug(
                            "Attempting to create and validate AssistantResponseMessage"
                        )
                        assistant_response_message = AssistantResponseMessage(
                            user_id=response_payload["user_id"],
                            status=response_payload.get("status", "error"),
                            response=response_payload.get("response"),
                            error=response_payload.get("error"),
                            source=response_payload.get("source"),
                        )
                        logger.debug(
                            "Attempting to serialize AssistantResponseMessage payload"
                        )
                        response_json = assistant_response_message.model_dump_json()
                        logger.debug("Successfully serialized AssistantResponseMessage")
                        logger.debug("Attempting to push response to Redis")
                        await self.redis.rpush(
                            self.settings.OUTPUT_QUEUE, response_json
                        )
                        logger.debug("Successfully pushed response to Redis")
                        logger.info(
                            "Response sent to output queue",
                            queue=self.settings.OUTPUT_QUEUE,
                            user_id=assistant_response_message.user_id,
                            status=assistant_response_message.status,
                            source=assistant_response_message.source,
                        )
                    except ValidationError as validation_err:
                        logger.error(
                            "Failed to validate assistant response data before sending to Redis",
                            payload=response_payload,
                            errors=validation_err.errors(),
                            exc_info=True,
                        )
                        # Do not send invalid message
                    except redis.RedisError as push_e:
                        logger.error(
                            f"Failed to push response to Redis queue {self.settings.OUTPUT_QUEUE}: {push_e}",
                            payload=response_payload,  # Log original dict
                            exc_info=True,
                        )
                    except (
                        TypeError
                    ) as json_err:  # Should not happen with model_dump_json
                        logger.error(
                            f"Failed to serialize AssistantResponseMessage payload to JSON: {json_err}",
                            payload=str(assistant_response_message)
                            if "assistant_response_message" in locals()
                            else str(response_payload),
                            exc_info=True,
                        )
                    else:
                        logger.error(
                            "Cannot send response, user_id is missing",
                            payload=response_payload,
                        )

                logger.debug("Incrementing processed_count")
                processed_count += 1
                if max_messages and processed_count >= max_messages:
                    logger.info(
                        f"Processed {processed_count}/{max_messages} messages. Stopping listener."
                    )
                    break

            except redis.RedisError as e:
                logger.error(f"Redis error during blpop or rpush: {e}", exc_info=True)
                time.sleep(1)
                continue
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to decode JSON message: {e}",
                    raw_message=raw_message_bytes.decode("utf-8", errors="ignore")
                    if raw_message_bytes
                    else None,
                )
            except Exception as e:
                logger.exception(
                    f"Unexpected error processing message loop: {e}", exc_info=True
                )
                # No user_id context available here, just log the error
                time.sleep(1)
                continue

        logger.info("Message listener finished.")

    async def close(self):
        """Close connections"""
        await self.redis.close()
        await self.rest_client.close()
        await self.factory.close()
        logger.info("Assistant orchestrator connections closed.")
