import json
import time
from typing import Optional
from uuid import UUID

import redis.asyncio as redis
from assistants.base_assistant import BaseAssistant
from assistants.factory import AssistantFactory
from config.logger import get_logger
from config.settings import Settings
from langchain_core.messages import HumanMessage, ToolMessage
from messages.queue_models import QueueMessage, QueueMessageSource, QueueMessageType
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
            decode_responses=True,
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
            content=queue_message.content,
            timestamp=queue_message.timestamp,
        )

        if queue_message.type == QueueMessageType.HUMAN:
            message = HumanMessage(
                content=queue_message.content.message,
                metadata=queue_message.content.metadata,
            )
            logger.info("Created human message", message=str(message))
            return message
        if queue_message.type == QueueMessageType.TOOL:
            message = ToolMessage(
                content=queue_message.content.message,
                tool_call_id=str(queue_message.timestamp.timestamp()),
                tool_name=queue_message.content.metadata.get("tool_name", "unknown"),
                metadata=queue_message.content.metadata,
            )
            logger.info("Created tool message", message=str(message))
            return message
        logger.error("Unsupported message type", type=queue_message.type)
        raise ValueError(f"Unsupported message type: {queue_message.type}")

    async def process_message(self, queue_message: QueueMessage) -> Optional[dict]:
        """Process an incoming message from queue using the correct thread_id."""
        user_id = None
        start_time = time.perf_counter()
        get_secretary_start_time = None
        process_message_start_time = None
        try:
            user_id = queue_message.user_id
            text = queue_message.content.message

            log_extra = {
                "user_id": user_id,
                "source": queue_message.source,
                "type": queue_message.type,
                "timestamp": queue_message.timestamp,
            }
            logger.info("Processing message", extra=log_extra)

            # Get user's secretary directly from the factory (which handles caching)
            logger.debug("Getting secretary from factory", extra=log_extra)
            get_secretary_start_time = time.perf_counter()
            secretary: BaseAssistant = await self.factory.get_user_secretary(user_id)
            get_secretary_duration = time.perf_counter() - get_secretary_start_time
            log_extra["get_secretary_duration_ms"] = round(
                get_secretary_duration * 1000
            )
            if not secretary:
                # Should not happen if factory raises ValueError on failure, but handle defensively
                logger.error(
                    "Failed to get secretary instance from factory", extra=log_extra
                )
                raise ValueError(f"Could not retrieve secretary for user {user_id}")

            logger.info(
                "Retrieved secretary via factory",
                assistant_name=secretary.name,
                extra=log_extra,
            )

            # Create appropriate message type
            message = self._create_message(queue_message)
            logger.debug(
                "Langchain message created",
                message_type=type(message).__name__,
                extra=log_extra,
            )

            # Process message with user's secretary
            logger.debug("Invoking secretary.process_message", extra=log_extra)
            process_message_start_time = time.perf_counter()
            response = await secretary.process_message(
                message=message, user_id=str(user_id)
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
                "source": queue_message.source.value,
                "type": queue_message.type.value,
                "metadata": queue_message.content.metadata or {},
            }
            total_duration = time.perf_counter() - start_time
            log_extra["total_processing_duration_ms"] = round(total_duration * 1000)
            logger.info("Message processing completed successfully", extra=log_extra)
            return result

        except (ValueError, TypeError, KeyError) as e:
            # Handle specific, expected errors during message processing/parsing
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "source": getattr(queue_message, "source", "unknown"),
                "type": getattr(queue_message, "type", "unknown"),
            }
            logger.warning(
                f"Error processing message due to invalid data/structure: {type(e).__name__}",
                error=str(e),
                extra=log_extra,
            )
            # Return specific error payload for bad data
            return {
                "user_id": user_id if user_id is not None else "unknown",
                "text": getattr(
                    getattr(queue_message, "content", None), "message", "unknown"
                ),
                "status": "error",
                # Provide a slightly more informative error message to the user
                "response": f"Message processing failed due to an internal error: {type(e).__name__}",
                "error": str(e),  # Keep detailed error for internal use/output queue
                "source": getattr(queue_message, "source", "unknown").value
                if hasattr(getattr(queue_message, "source", None), "value")
                else "unknown",
                "type": getattr(queue_message, "type", "unknown").value
                if hasattr(getattr(queue_message, "type", None), "value")
                else "unknown",
                "metadata": getattr(
                    getattr(queue_message, "content", None), "metadata", None
                )
                or {},
            }
        except Exception as e:
            total_duration = time.perf_counter() - start_time
            log_extra = {
                "user_id": user_id if user_id is not None else "unknown",
                "source": getattr(queue_message, "source", "unknown"),
                "type": getattr(queue_message, "type", "unknown"),
            }
            logger.exception(
                "Message processing failed",
                error=str(e),
                exc_info=True,
                extra=log_extra,
            )
            # No need to remove from orchestrator cache
            # if user_id is not None:
            #     removed_assistant = self.secretaries.pop(user_id, None)
            #     if removed_assistant:
            #         logger.warning(
            #             f"Removed secretary instance for user {user_id} from cache due to processing error.",
            #             extra=log_extra,
            #         )

            # Return an error payload
            return {
                "user_id": user_id if user_id is not None else "unknown",
                "text": getattr(
                    getattr(queue_message, "content", None), "message", "unknown"
                ),
                "status": "error",
                # Provide a slightly more informative error message to the user
                "response": f"Message processing failed due to an internal error: {type(e).__name__}",
                "error": str(e),  # Keep detailed error for internal use/output queue
                "source": getattr(queue_message, "source", "unknown").value
                if hasattr(getattr(queue_message, "source", None), "value")
                else "unknown",
                "type": getattr(queue_message, "type", "unknown").value
                if hasattr(getattr(queue_message, "type", None), "value")
                else "unknown",
                "metadata": getattr(
                    getattr(queue_message, "content", None), "metadata", None
                )
                or {},
            }

    async def handle_reminder_trigger(
        self, reminder_event_data: dict
    ) -> Optional[dict]:
        """Handles the 'reminder_triggered' event from Redis."""
        start_time = time.perf_counter()
        get_secretary_start_time = None
        process_message_start_time = None
        log_extra = {"event_type": "reminder_triggered"}
        logger.info(
            "Handling reminder trigger event",
            data_preview=str(reminder_event_data)[:100],
            extra=log_extra,
        )
        user_id = None
        reminder_id = None
        try:
            # 1. Extract data safely from QueueMessage structure
            content_dict = reminder_event_data.get("content", {})
            metadata_dict = content_dict.get("metadata", {})

            user_id_str = reminder_event_data.get("user_id")  # User ID is top-level
            assistant_uuid_str = metadata_dict.get("assistant_id")
            reminder_id = metadata_dict.get("reminder_id")
            reminder_payload = metadata_dict.get("payload", {})  # Inner payload is here
            reminder_type = metadata_dict.get("reminder_type")
            triggered_at_event = metadata_dict.get("triggered_at_event")

            # Convert user_id to int (or handle potential error)
            user_id = None
            if user_id_str is not None:
                try:
                    user_id = int(user_id_str)
                except ValueError:
                    logger.error(
                        "Invalid user_id format in reminder event",
                        user_id_str=user_id_str,
                        extra=log_extra,
                    )
                    return None  # Or raise error

            log_extra["user_id"] = user_id  # Log the potentially converted ID
            log_extra["reminder_id"] = reminder_id
            log_extra["assistant_id"] = assistant_uuid_str  # Keep as string for now

            if not all(
                [assistant_uuid_str, user_id is not None, reminder_id]
            ):  # Check if user_id conversion succeeded
                logger.error(
                    "Missing required fields after parsing reminder event",
                    parsed_user_id=user_id,
                    parsed_assistant_id=assistant_uuid_str,
                    parsed_reminder_id=reminder_id,
                    original_data=reminder_event_data,
                    extra=log_extra,
                )
                return None

            # Convert assistant_id to UUID
            try:
                assistant_uuid = UUID(assistant_uuid_str)
                log_extra["assistant_uuid"] = str(assistant_uuid)
            except ValueError:
                logger.error(
                    "Invalid Assistant UUID format",
                    assistant_id=assistant_uuid_str,
                    extra=log_extra,
                )
                return None

            logger.debug("Extracted reminder data successfully", extra=log_extra)

            # 2. Get assistant instance (user's secretary) via factory
            logger.debug("Getting secretary for reminder", extra=log_extra)
            get_secretary_start_time = time.perf_counter()
            # Secretary should now be LangGraphAssistant type for direct graph access
            secretary: BaseAssistant = (
                await self.factory.get_user_secretary(  # Use BaseAssistant type hint
                    user_id  # Pass integer user_id
                )
            )
            get_secretary_duration = time.perf_counter() - get_secretary_start_time
            log_extra["get_secretary_duration_ms"] = round(
                get_secretary_duration * 1000
            )
            if not secretary:
                # Should not happen if factory raises ValueError, but double-check
                logger.error(
                    "Secretary not found for user via factory", user_id=user_id
                )
                return None  # Indicate error or skip processing
            # Remove check for compiled_graph as we rely on BaseAssistant interface
            # if not hasattr(secretary, 'compiled_graph'):
            #     logger.error(...)
            #     return None

            logger.info(
                "Retrieved secretary instance via factory for reminder",
                assistant_name=secretary.name,
                user_id=user_id,
            )

            # 3. Prepare trigger event data
            reminder_trigger_data = {
                # "event_type": "reminder_triggered", # This field is not strictly needed for the graph state
                "reminder_id": reminder_id,
                "assistant_id": str(assistant_uuid),
                "reminder_type": reminder_type,
                "payload": reminder_payload,  # Contains the user-facing message
                "trigger_timestamp_utc": triggered_at_event,
            }
            logger.info(
                "Prepared reminder trigger data",
                trigger_data=reminder_trigger_data,
                extra=log_extra,
            )

            # 4. Invoke the secretary's process_message with the trigger event
            logger.debug(
                "Invoking secretary.process_message for reminder trigger",
                extra=log_extra,
            )
            process_message_start_time = time.perf_counter()
            # Pass None for message, but provide triggered_event
            response_text = await secretary.process_message(
                message=None,  # No direct message from user
                user_id=str(user_id),  # Pass user_id for context/threading
                triggered_event=reminder_trigger_data,  # Pass the trigger data
            )
            process_message_duration = time.perf_counter() - process_message_start_time
            log_extra["process_message_duration_ms"] = round(
                process_message_duration * 1000
            )

            logger.info(
                "Secretary processed reminder trigger",
                response_preview=str(response_text)[:100],
                extra=log_extra,
            )

            # 5. Format response for output queue
            response_payload = {
                "user_id": user_id,
                "response": response_text,  # The actual response string from the secretary
                "status": "success",
                "source": "reminder_trigger",  # Indicate the source
                "type": "assistant",  # Indicate the type is an assistant response
                "metadata": {  # Include reminder ID for context if needed downstream
                    "reminder_id": reminder_id
                },
            }
            logger.debug(
                "Reminder response payload prepared",
                payload=response_payload,
                extra=log_extra,
            )

            total_duration = time.perf_counter() - start_time
            log_extra["total_processing_duration_ms"] = round(total_duration * 1000)
            logger.info(
                "Reminder trigger processed successfully",
                reminder_id=reminder_id,
                user_id=user_id,
                extra=log_extra,
            )
            return response_payload

        except (ValueError, TypeError, KeyError) as e:
            # Handle specific errors during data extraction or processing
            log_extra.update(
                {
                    "user_id": user_id if user_id is not None else "unknown",
                    "reminder_id": reminder_id
                    if reminder_id is not None
                    else "unknown",
                }
            )
            logger.warning(
                f"Error handling reminder trigger due to invalid data: {type(e).__name__}",
                error=str(e),
                extra=log_extra,
            )
            # Optionally return an error payload
            return {
                "user_id": user_id if user_id is not None else "unknown",
                "status": "error",
                "response": f"Failed to process reminder trigger: {type(e).__name__}",
                "error": str(e),
                "source": "reminder_trigger",
                "type": "error",
                "metadata": {"reminder_id": reminder_id if reminder_id else "unknown"},
            }

        except Exception as e:
            # Catch-all for unexpected errors
            total_duration = time.perf_counter() - start_time
            log_extra.update(
                {
                    "user_id": user_id if user_id is not None else "unknown",
                    "reminder_id": reminder_id
                    if reminder_id is not None
                    else "unknown",
                    "total_processing_duration_ms": round(total_duration * 1000),
                }
            )
            logger.exception(
                "Unexpected error handling reminder trigger",
                error=str(e),
                exc_info=True,
                extra=log_extra,
            )
            # Return an error payload
            return {
                "user_id": user_id if user_id is not None else "unknown",
                "status": "error",
                "response": f"Internal error processing reminder trigger: {type(e).__name__}",
                "error": str(e),
                "source": "reminder_trigger",
                "type": "error",
                "metadata": {"reminder_id": reminder_id if reminder_id else "unknown"},
            }

    async def listen_for_messages(self, max_messages: int | None = None):
        """Listen for incoming messages from Redis queue and dispatch processing."""
        logger.info(
            "Starting message listener",
            input_queue=self.settings.INPUT_QUEUE,
            output_queue=self.settings.OUTPUT_QUEUE,
            max_messages=max_messages if max_messages else "unlimited",
        )
        processed_count = 0
        while max_messages is None or processed_count < max_messages:
            raw_message = None
            try:
                # logger.debug(
                #     "Waiting for message in queue", queue=self.settings.INPUT_QUEUE
                # )
                message_data = await self.redis.blpop(
                    self.settings.INPUT_QUEUE, timeout=5
                )

                if not message_data:
                    continue

                _, raw_message = message_data
                logger.debug(
                    "Raw message received", message_json_preview=raw_message[:100]
                )
                message_dict = json.loads(raw_message)

                response_payload = None

                # --- Corrected Trigger Identification Logic ---
                is_trigger = False
                if (
                    message_dict.get("source") == QueueMessageSource.CRON.value
                    and message_dict.get("type") == QueueMessageType.TOOL.value
                ):
                    # Further check based on metadata if needed
                    metadata = message_dict.get("content", {}).get("metadata", {})
                    if metadata.get("tool_name") == "reminder_trigger":
                        is_trigger = True

                if is_trigger:
                    # Handle reminder trigger
                    user_id = message_dict.get("user_id")  # Get user_id for logging
                    if user_id:
                        logger.info(
                            f"Reminder trigger event (identified by source/type/tool_name) received for user {user_id}",
                        )
                        # Pass the original dictionary to handle_reminder_trigger
                        response_payload = await self.handle_reminder_trigger(
                            message_dict
                        )
                    else:
                        # This check is also inside handle_reminder_trigger, log here for context
                        logger.error(
                            "User ID missing in reminder event payload (check in listen_for_messages)",
                            data=message_dict,
                        )
                else:
                    # Handle standard QueueMessage
                    try:
                        queue_message = QueueMessage(**message_dict)
                        user_id = queue_message.user_id
                        logger.info(
                            f"Standard queue message received for user {queue_message.user_id}",
                        )
                        response_payload = await self.process_message(queue_message)
                    except Exception as parse_exc:
                        logger.error(
                            f"Failed to parse standard message: {parse_exc}",
                            raw_message=raw_message,
                            exc_info=True,
                        )

                # Send response if generated
                if response_payload:
                    try:
                        await self.redis.rpush(
                            self.settings.OUTPUT_QUEUE, json.dumps(response_payload)
                        )
                        logger.info(
                            "Response sent to output queue",
                            queue=self.settings.OUTPUT_QUEUE,
                            user_id=response_payload.get("user_id"),
                            status=response_payload.get("status"),
                        )
                    except redis.RedisError as push_e:
                        logger.error(
                            f"Failed to push response to Redis queue {self.settings.OUTPUT_QUEUE}: {push_e}",
                            payload=response_payload,
                            exc_info=True,
                        )

                processed_count += 1
                if max_messages:
                    logger.debug(
                        f"Processed {processed_count}/{max_messages} messages."
                    )

            except redis.RedisError as e:
                logger.error(f"Redis error during blpop or rpush: {e}", exc_info=True)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to decode JSON message: {e}", raw_message=raw_message
                )
            except Exception as e:
                logger.exception(
                    f"Unexpected error processing message loop: {e}", exc_info=True
                )

        logger.info("Message listener finished.")

    async def close(self):
        """Close connections"""
        await self.redis.close()
        await self.rest_client.close()
        await self.factory.close()
