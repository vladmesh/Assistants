import json
from typing import Dict

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

                    queue_message = QueueMessage.from_dict(message_data)
                    logger.info("Parsed queue message", message=queue_message)

                    # Process message
                    response = await self.process_message(queue_message)
                    logger.info("Message processed", response=response)

                    # Send response to output queue
                    await self.redis.rpush(
                        self.settings.OUTPUT_QUEUE, json.dumps(response)
                    )
                    logger.info("Response sent to output queue", response=response)

                    messages_processed += 1
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
