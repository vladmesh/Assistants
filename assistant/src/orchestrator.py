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
            # Get secretary assistant
            logger.info("Getting assistants")
            assistants = await self.rest_client.get_assistants()
            logger.info("Assistants fetched", 
                       assistant_count=len(assistants))
            secretary = next((a for a in assistants if a.is_secretary), None)
            if not secretary:
                raise ValueError("Secretary assistant not found")
            
            # Get tools for secretary
            logger.info("Getting tools for secretary")
            secretary_tools = await self.rest_client.get_assistant_tools(str(secretary.id))
            logger.info("Tools fetched", 
                       tool_count=len(secretary_tools))
            
            # Initialize tools based on their types
            for tool_data in secretary_tools:
                logger.info("Initializing tool", 
                           tool_name=tool_data.name,
                           tool_type=tool_data.tool_type)
                
                # Convert REST service tool data to RestServiceTool
                tool_dict = tool_data.dict()
                tool_dict['settings'] = self.settings
                logger.info("Tool data from REST service", tool_dict=tool_dict)
                rest_tool = RestServiceTool(**tool_dict)
                
                # Convert to actual tool
                tool = rest_tool.to_tool()
                
                # For sub_assistant type, get and set the sub-assistant
                if rest_tool.tool_type == "sub_assistant":
                    logger.info("Creating sub_assistant tool",
                               assistant_id=rest_tool.assistant_id)
                    sub_assistant = await self.rest_client.get_assistant(rest_tool.assistant_id)
                    logger.info("Got sub_assistant from REST service",
                               assistant_id=sub_assistant.id,
                               name=sub_assistant.name)
                    sub_assistant_instance = await self.factory.create_sub_assistant(sub_assistant)
                    logger.info("Created sub_assistant instance",
                               assistant_id=sub_assistant_instance.assistant_id,
                               name=sub_assistant_instance.name)
                    tool.sub_assistant = sub_assistant_instance
                    tool.assistant_id = rest_tool.assistant_id
                    logger.info("Set sub_assistant in tool",
                               tool_assistant_id=tool.assistant_id,
                               tool_name=tool.name)
                
                self.tools.append(tool)
                logger.info("Added tool", name=tool.name)
            
            # Log all tools before creating assistant
            logger.info("All tools initialized", 
                       tool_count=len(self.tools),
                       tool_names=[tool.name for tool in self.tools])
            
            # Initialize main assistant
            self.assistant = await self.factory.create_main_assistant(self.tools)
            
            logger.info("Assistant service initialized with tools",
                       tool_count=len(self.tools))
            
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