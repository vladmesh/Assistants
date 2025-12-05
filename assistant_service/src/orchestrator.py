import asyncio
import json
import time

import redis.asyncio as redis
from langchain_core.messages import HumanMessage
from pydantic import ValidationError
from shared_models import AssistantResponseMessage, QueueMessage, QueueTrigger

from assistants.base_assistant import BaseAssistant
from assistants.factory import AssistantFactory
from config.logger import get_logger
from config.settings import Settings
from services.rest_service import RestServiceClient

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

        logger.info(
            "Assistant service initialized",
        )

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
            timestamp_iso = event.timestamp.isoformat()

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
        logger.info(
            "Starting message listener",
            input_queue=self.settings.INPUT_QUEUE,
            output_queue=self.settings.OUTPUT_QUEUE,
        )
        while True:
            raw_message_bytes = None
            response_payload = None  # Initialize response_payload here
            event_object: QueueMessage | QueueTrigger | None = (
                None  # To hold parsed object
            )

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
                    extra={"message_json_preview": raw_message_json[:200]},
                )

                message_dict = json.loads(raw_message_json)
                logger.debug(
                    "Successfully parsed JSON",
                    extra={"keys": list(message_dict.keys())},
                )

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
                    response_payload = await self._dispatch_event(event_object)
                else:
                    # Parsing failed or structure was invalid
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

                # Send response if any
                if response_payload:
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
                        await self.redis.rpush(
                            self.settings.OUTPUT_QUEUE, response_json
                        )
                        logger.info(
                            "Response sent to output queue",
                            user_id=response_payload.get("user_id"),
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
                await asyncio.sleep(5)  # Wait before retrying connection
            except Exception as e:
                logger.error(
                    f"Error in message listener loop: {e}",
                    exc_info=True,
                    raw_message=raw_message_bytes.decode("utf-8", errors="ignore")
                    if raw_message_bytes
                    else "N/A",
                )
                # Avoid tight loop on persistent errors
                await asyncio.sleep(1)

    async def close(self):
        """Close Redis connection."""
        await self.redis.close()
        logger.info("Redis connection closed.")
