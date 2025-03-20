import json
import redis.asyncio as redis
from config.logger import get_logger
from config.settings import Settings
from tools.rest_service_tool import RestServiceTool
from assistants.factory import AssistantFactory
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
            decode_responses=True
        )
        
        self.settings = settings
        self.rest_client = RestServiceClient()
        self.factory = AssistantFactory(settings)
        
        # Initialize tools and assistant
        self.tools = []
        self.assistant = None
        
        logger.info("Assistant service initialized")
    
    async def initialize(self):
        """Initialize tools and assistant from REST service"""
        try:
            # Initialize main assistant with tools
            self.assistant = await self.factory.create_main_assistant()
            
            logger.info("Assistant service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize assistant service",
                        error=str(e),
                        exc_info=True)
            raise
    
    async def process_message(self, message: dict) -> dict:
        """Process an incoming message."""
        try:
            # Get message data
            user_id = str(message.get("user_id", ""))
            text = message.get("text", "")
            
            # Set user context for tools
            for tool in self.tools:
                if hasattr(tool, 'user_id'):
                    tool.user_id = user_id
            
            logger.info("Processing message",
                       user_id=user_id,
                       message_length=len(text))
            
            response = await self.assistant.process_message(text, user_id)
            
            return {
                "user_id": user_id,
                "text": text,
                "response": response,
                "status": "success"
            }
            
        except Exception as e:
            logger.error("Message processing failed",
                        error=str(e),
                        exc_info=True)
            return {
                "user_id": message.get("user_id", ""),
                "text": message.get("text", ""),
                "status": "error",
                "error": str(e)
            }
            
    async def listen_for_messages(self):
        """Listen for messages from Redis queue."""
        try:
            await self.initialize()
            
            logger.info("Starting message listener",
                       input_queue=self.settings.INPUT_QUEUE,
                       output_queue=self.settings.OUTPUT_QUEUE)
            
            while True:
                try:
                    # Get message from input queue
                    message = await self.redis.blpop(self.settings.INPUT_QUEUE)
                    if not message:
                        continue
                        
                    # Parse message
                    message_data = json.loads(message[1])
                    
                    # Process message
                    response = await self.process_message(message_data)
                    
                    # Send response to output queue
                    await self.redis.rpush(
                        self.settings.OUTPUT_QUEUE,
                        json.dumps(response)
                    )
                    
                except Exception as e:
                    logger.error("Error processing message",
                                error=str(e),
                                exc_info=True)
                    continue
                    
        except Exception as e:
            logger.error("Message listener failed",
                        error=str(e),
                        exc_info=True)
            raise
            
    async def close(self):
        """Close connections"""
        await self.redis.close()
        await self.rest_client.close()
        await self.factory.close() 