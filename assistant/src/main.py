import os
import json
import asyncio
from typing import Dict, Any
import redis.asyncio as redis
from dotenv import load_dotenv

from assistants.openai_assistant import OpenAIAssistant
from tools.time_tool import TimeToolWrapper
from tools.reminder_tool import ReminderTool
from config.settings import settings
from config.logger import configure_logger, get_logger
from config.instructions import ASSISTANT_INSTRUCTIONS

# Configure logger
configure_logger(settings.ENVIRONMENT)
logger = get_logger(__name__)

# Load environment variables
load_dotenv()

class AssistantOrchestrator:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )
        
        # Initialize tools
        self.tools = [
            TimeToolWrapper(),
            ReminderTool()
        ]
        
        # Initialize OpenAI assistant
        self.assistant = OpenAIAssistant(
            assistant_id=settings.OPEN_API_SECRETAR_ID,
            name="Секретарь",
            instructions=ASSISTANT_INSTRUCTIONS,
            model="gpt-4-1106-preview",
            tools=[tool.openai_schema for tool in self.tools],
            tool_instances=self.tools
        )
        logger.info("Assistant orchestrator initialized", tools_count=len(self.tools))
    
    async def process_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message and return the response."""
        try:
            logger.info("Processing message", 
                       user_id=data["user_id"],
                       chat_id=data.get("chat_id"),
                       message_length=len(data["message"]))
            
            result = await self.assistant.process_message(
                message=data["message"],
                user_id=str(data["user_id"])  # Convert to string as tools expect string user_id
            )
            
            logger.info("Message processed successfully",
                       user_id=data["user_id"],
                       chat_id=data.get("chat_id"))
            
            return {
                "user_id": data["user_id"],
                "chat_id": data.get("chat_id"),
                "status": "success",
                "response": result,
                "error": None
            }
        except Exception as e:
            logger.error("Error processing message",
                        user_id=data["user_id"],
                        chat_id=data.get("chat_id"),
                        error=str(e),
                        exc_info=True)
            
            return {
                "user_id": data["user_id"],
                "chat_id": data.get("chat_id"),
                "status": "error",
                "response": None,
                "error": str(e)
            }
    
    async def listen_for_messages(self):
        """Listen for messages in the Redis queue."""
        logger.info("Starting message listener")
        while True:
            try:
                # Get message from input queue
                _, message = await self.redis.brpop("telegram_input_queue")
                data = json.loads(message)
                
                # Process message
                result = await self.process_message(data)
                
                # Send result to output queue
                await self.redis.lpush("telegram_output_queue", json.dumps(result))
                
            except Exception as e:
                logger.error("Error in message listener", error=str(e), exc_info=True)
                continue

async def main():
    logger.info("Starting assistant service", environment=settings.ENVIRONMENT)
    orchestrator = AssistantOrchestrator()
    await orchestrator.listen_for_messages()

if __name__ == "__main__":
    asyncio.run(main()) 