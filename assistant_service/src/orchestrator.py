import asyncio
import json
from typing import Dict
from uuid import UUID

import redis.asyncio as redis
from assistants.base import BaseAssistant
from assistants.factory import AssistantFactory
from config.logger import get_logger
from config.settings import Settings
from messages.base import HumanMessage, ToolMessage
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
        self.factory = AssistantFactory(settings)
        self.secretaries: Dict[int, BaseAssistant] = {}

        logger.info("Assistant service initialized")

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

    async def process_message(self, queue_message: QueueMessage) -> dict:
        """Process an incoming message from queue."""
        try:
            user_id = queue_message.user_id
            text = queue_message.content.message

            logger.info(
                "Processing message",
                user_id=user_id,
                message_length=len(text),
                source=queue_message.source,
                type=queue_message.type,
                content=queue_message.content,
                timestamp=queue_message.timestamp,
            )

            # Get user's secretary
            if user_id in self.secretaries:
                secretary = self.secretaries[user_id]
                logger.info("Using existing secretary", user_id=user_id)
            else:
                logger.info("Creating new secretary", user_id=user_id)
                secretary = await self.factory.get_user_secretary(user_id)
                self.secretaries[user_id] = secretary
                logger.info("Secretary created", user_id=user_id)

            # Create appropriate message type
            message = self._create_message(queue_message)
            logger.info("Message created", message=str(message))

            # Process message with user's secretary
            logger.info("Processing message with secretary", user_id=user_id)
            response = await secretary.process_message(message, str(user_id))
            logger.info("Secretary response received", response=response)

            result = {
                "user_id": user_id,
                "text": text,
                "response": response,
                "status": "success",
                "source": queue_message.source,
                "type": queue_message.type,
                "metadata": queue_message.content.metadata,
            }
            logger.info("Message processing completed", result=result)
            return result

        except Exception as e:
            logger.error(
                "Message processing failed",
                error=str(e),
                user_id=queue_message.user_id,
                content=queue_message.content,
                exc_info=True,
            )
            return {
                "user_id": queue_message.user_id,
                "text": queue_message.content.message,
                "status": "error",
                "error": str(e),
                "source": queue_message.source,
                "type": queue_message.type,
            }

    async def handle_reminder_trigger(self, reminder_event_data: dict):
        """Handles the 'reminder_triggered' event from Redis by treating it as a ToolMessage."""
        logger.info("Handling reminder trigger event", data=reminder_event_data)
        try:
            # 1. Extract data
            event_payload = reminder_event_data.get("payload", {})
            assistant_uuid_str = reminder_event_data.get("assistant_id")
            user_id = event_payload.get("user_id")
            reminder_id = event_payload.get("reminder_id")
            reminder_payload = event_payload.get(
                "payload", {}
            )  # The actual inner payload

            if not all([assistant_uuid_str, user_id, reminder_id]):
                logger.error(
                    "Missing required fields in reminder event",
                    data=reminder_event_data,
                )
                return  # Or raise an error?

            # Convert assistant_id to UUID
            try:
                assistant_uuid = UUID(assistant_uuid_str)
            except ValueError:
                logger.error(
                    "Invalid Assistant UUID format", assistant_id=assistant_uuid_str
                )
                return

            logger.info(
                "Extracted reminder data",
                assistant_id=assistant_uuid,
                user_id=user_id,
                reminder_id=reminder_id,
            )

            # 2. Get assistant instance
            try:
                # Use the new factory method
                # assistant = await self.factory.get_assistant_by_id(assistant_uuid)

                # Get the user's current secretary instead
                secretary = await self.factory.get_user_secretary(user_id)

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
                metadata=metadata,
            )
            logger.info("Constructed ToolMessage", message=str(tool_message))

            # 4. Call assistant.process_message (use the retrieved secretary)
            response_text = await secretary.process_message(tool_message, str(user_id))
            logger.info("Secretary processed reminder trigger", response=response_text)

            # 5. Send the response to the output queue (e.g., to Telegram)
            if response_text:  # Only send if assistant generated a response
                response_payload = {
                    "user_id": user_id,  # Use the user_id from the event
                    "response": response_text,
                    "status": "success",
                    "source": "reminder_trigger",  # Indicate source
                    "type": "assistant",  # Or a new type?
                    "metadata": {  # Include reminder info in metadata if needed
                        "reminder_id": reminder_id
                    },
                }
                await self.redis.rpush(
                    self.settings.OUTPUT_QUEUE, json.dumps(response_payload)
                )
                logger.info(
                    "Sent reminder response to output queue", response=response_payload
                )
            else:
                logger.info(
                    "Assistant did not generate a response for reminder trigger"
                )

        except Exception as e:
            logger.error(
                "Failed to handle reminder trigger",
                error=str(e),
                data=reminder_event_data,
                exc_info=True,
            )
            # Optionally send an error message somewhere?

    async def listen_for_messages(self, max_messages: int | None = None):
        """Listen for messages from Redis queue."""
        try:
            logger.info(
                "Starting message listener",
                input_queue=self.settings.INPUT_QUEUE,
                output_queue=self.settings.OUTPUT_QUEUE,
                max_messages=max_messages,
            )

            messages_processed = 0
            while True:
                try:
                    # Get message from input queue
                    logger.debug(
                        "Waiting for message in queue", queue=self.settings.INPUT_QUEUE
                    )
                    message = await self.redis.blpop(self.settings.INPUT_QUEUE)
                    if not message:
                        continue

                    # Parse and validate message
                    message_data = json.loads(message[1])
                    logger.info("Received message from queue", message=message_data)

                    # Check for reminder trigger event
                    if message_data.get("event") == "reminder_triggered":
                        logger.info(
                            "Handling reminder trigger event", message=message_data
                        )
                        # Placeholder for actual handling logic
                        await self.handle_reminder_trigger(message_data)
                        # Decide if we need to send a response or not for reminders
                        # For now, we assume handle_reminder_trigger sends necessary responses
                        messages_processed += 1  # Count as processed

                    # Handle regular messages (Human/Tool)
                    else:
                        try:
                            queue_message = QueueMessage.from_dict(message_data)
                            logger.info("Parsed queue message", message=queue_message)
                            response = await self.process_message(queue_message)
                            logger.info("Message processed", response=response)
                            await self.redis.rpush(
                                self.settings.OUTPUT_QUEUE, json.dumps(response)
                            )
                            logger.info(
                                "Response sent to output queue", response=response
                            )
                            messages_processed += 1
                        except ValueError as val_err:
                            logger.error(
                                "Invalid message format, skipping",
                                error=str(val_err),
                                message=message_data,
                            )
                            # Do not count as processed if format is invalid
                            continue

                    if max_messages and messages_processed >= max_messages:
                        logger.info(
                            f"Processed {max_messages} messages, stopping listener"
                        )
                        break

                except Exception as e:
                    logger.error(
                        "Error processing message",
                        error=str(e),
                        message=message[1] if message else None,
                        exc_info=True,
                    )
                    continue

        except Exception as e:
            logger.error("Message listener failed", error=str(e), exc_info=True)
            raise

    async def close(self):
        """Close connections"""
        await self.redis.close()
        await self.rest_client.close()
        await self.factory.close()
