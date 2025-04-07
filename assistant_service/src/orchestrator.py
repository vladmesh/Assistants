import json
from typing import Dict, Optional
from uuid import UUID

import redis.asyncio as redis
from assistants.base import BaseAssistant
from assistants.factory import AssistantFactory
from config.logger import get_logger
from config.settings import Settings
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from messages.queue_models import QueueMessage, QueueMessageType
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
        # Create a checkpointer instance (using MemorySaver for now)
        self.checkpointer = MemorySaver()
        # Pass checkpointer to the factory
        self.factory = AssistantFactory(settings, checkpointer=self.checkpointer)
        # Restore the orchestrator-level secretary cache
        self.secretaries: Dict[int, BaseAssistant] = {}

        logger.info(
            "Assistant service initialized",
            checkpointer=type(self.checkpointer).__name__,
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
        else:
            logger.error("Unsupported message type", type=queue_message.type)
            raise ValueError(f"Unsupported message type: {queue_message.type}")

    async def process_message(
        self, queue_message: QueueMessage, thread_id: str
    ) -> Optional[dict]:
        """Process an incoming message from queue using the correct thread_id."""
        try:
            user_id = queue_message.user_id
            text = queue_message.content.message

            log_extra = {
                "user_id": user_id,
                "thread_id": thread_id,
                "source": queue_message.source,
                "type": queue_message.type,
                "timestamp": queue_message.timestamp,
            }
            logger.info("Processing message", extra=log_extra)

            # Get user's secretary using the orchestrator cache
            if user_id in self.secretaries:
                secretary: BaseAssistant = self.secretaries[user_id]
                logger.debug(
                    "Using existing secretary from orchestrator cache", extra=log_extra
                )
            else:
                logger.info(
                    "Secretary not in cache, getting from factory", extra=log_extra
                )
                secretary: BaseAssistant = await self.factory.get_user_secretary(
                    user_id
                )
                self.secretaries[user_id] = secretary
                logger.info(
                    "Retrieved secretary via factory and cached",
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

            # Process message with user's secretary, passing thread_id
            logger.debug("Invoking secretary.process_message", extra=log_extra)
            response = await secretary.process_message(
                message, str(user_id), thread_id=thread_id
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
            logger.info("Message processing completed successfully", extra=log_extra)
            return result

        except Exception as e:
            log_extra = {
                "user_id": getattr(queue_message, "user_id", "unknown"),
                "thread_id": thread_id,
                "source": getattr(queue_message, "source", "unknown"),
                "type": getattr(queue_message, "type", "unknown"),
            }
            logger.exception(
                "Message processing failed",
                error=str(e),
                exc_info=True,
                extra=log_extra,
            )
            return {
                "user_id": getattr(queue_message, "user_id", "unknown"),
                "text": getattr(
                    getattr(queue_message, "content", None), "message", "unknown"
                ),
                "status": "error",
                "error": str(e),
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
        self, reminder_event_data: dict, thread_id: str
    ) -> Optional[dict]:
        """Handles the 'reminder_triggered' event from Redis."""
        log_extra = {"thread_id": thread_id, "event_type": "reminder_triggered"}
        logger.info(
            "Handling reminder trigger event",
            data_preview=str(reminder_event_data)[:100],
            extra=log_extra,
        )
        user_id = None
        reminder_id = None
        try:
            # 1. Extract data safely
            event_payload = reminder_event_data.get("payload", {})
            assistant_uuid_str = reminder_event_data.get("assistant_id")
            user_id = event_payload.get("user_id")
            reminder_id = event_payload.get("reminder_id")
            reminder_payload = event_payload.get("payload", {})

            log_extra["user_id"] = user_id
            log_extra["reminder_id"] = reminder_id
            log_extra["assistant_id"] = assistant_uuid_str

            if not all([assistant_uuid_str, user_id, reminder_id]):
                logger.error(
                    "Missing required fields in reminder event",
                    data=reminder_event_data,
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

            logger.debug("Extracted reminder data", extra=log_extra)

            # 2. Get assistant instance
            try:
                # Use the new factory method
                # assistant = await self.factory.get_assistant_by_id(assistant_uuid)

                # Get the user's current secretary instead
                secretary: BaseAssistant = await self.factory.get_user_secretary(
                    user_id
                )

                if not secretary:
                    # Should not happen if factory raises ValueError, but double-check
                    logger.error("Secretary not found for user", user_id=user_id)
                    return
                logger.info(
                    "Retrieved secretary instance for user",
                    assistant_name=secretary.name,
                    user_id=user_id,
                )
            except ValueError as e:
                logger.error(f"Failed to get secretary instance: {e}", user_id=user_id)
                return
            except Exception as e:
                logger.error(
                    f"Unexpected error getting secretary: {e}",
                    user_id=user_id,
                    exc_info=True,
                )
                return

            # 3. Construct ToolMessage
            tool_name = "reminder_trigger"
            tool_call_id = str(reminder_id)  # Use reminder_id as unique ID
            # Create a descriptive content string
            content_str = f"Reminder triggered. Details: {json.dumps(reminder_payload)}"

            # Prepare metadata
            metadata = {
                "tool_name": tool_name,
                "original_event": reminder_event_data,  # Store the original event for context
            }

            tool_message = ToolMessage(
                content=content_str,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
            )
            logger.debug(
                "Constructed ToolMessage",
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                extra=log_extra,
            )

            # 4. Call secretary.process_message, passing thread_id
            response_text = await secretary.process_message(
                tool_message, str(user_id), thread_id=thread_id
            )
            logger.info(
                "Secretary processed reminder trigger",
                response_preview=str(response_text)[:100],
                extra=log_extra,
            )

            # 5. Prepare response payload for the output queue
            if response_text:
                response_payload = {
                    "user_id": user_id,
                    "response": response_text,
                    "status": "success",
                    "source": "reminder_trigger",
                    "type": "assistant",
                    "metadata": {"reminder_id": reminder_id},
                }
                logger.debug(
                    "Reminder response payload prepared",
                    payload=response_payload,
                    extra=log_extra,
                )
                return response_payload
            else:
                logger.info(
                    "Assistant did not generate a response for reminder trigger",
                    extra=log_extra,
                )
                return None

        except Exception as e:
            log_extra["user_id"] = user_id
            logger.exception(
                "Failed to process reminder trigger",
                error=str(e),
                exc_info=True,
                extra=log_extra,
            )
            return {
                "user_id": user_id if user_id else "unknown",
                "status": "error",
                "error": f"Failed to process reminder {reminder_id}: {str(e)}",
                "source": "reminder_trigger",
                "type": "system_error",
                "metadata": {"reminder_id": reminder_id} if reminder_id else {},
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
                logger.debug(
                    "Waiting for message in queue", queue=self.settings.INPUT_QUEUE
                )
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

                # Determine message type and generate thread_id
                if message_dict.get("event_type") == "reminder_triggered":
                    user_id = message_dict.get("payload", {}).get("user_id")
                    if user_id:
                        thread_id = f"reminder_user_{user_id}"
                        logger.info(
                            f"Reminder trigger event received for user {user_id}",
                            thread_id=thread_id,
                        )
                        response_payload = await self.handle_reminder_trigger(
                            message_dict, thread_id
                        )
                    else:
                        logger.error(
                            "User ID missing in reminder event payload",
                            data=message_dict,
                        )

                else:
                    # Assume standard QueueMessage
                    try:
                        queue_message = QueueMessage(**message_dict)
                        thread_id = f"user_{queue_message.user_id}"
                        logger.info(
                            f"Standard queue message received for user {queue_message.user_id}",
                            thread_id=thread_id,
                        )
                        response_payload = await self.process_message(
                            queue_message, thread_id
                        )
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
