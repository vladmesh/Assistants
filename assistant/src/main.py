from openai import OpenAI
import os
import json
import asyncio
import redis.asyncio as redis
from dotenv import load_dotenv
from config.logger import get_logger
from config.settings import get_settings
from config.instructions import ASSISTANT_INSTRUCTIONS
from assistants.openai_assistant import OpenAIAssistant
from assistants.sub_assistant import SubAssistant
from tools.time_tool import TimeToolWrapper
from tools.sub_assistant_tool import SubAssistantTool
from tools.reminder_tool import ReminderTool
logger = get_logger(__name__)
load_dotenv()

class AssistantOrchestrator:
    def __init__(self):
        """Initialize the assistant service."""
        settings = get_settings()
        
        # Initialize Redis connection
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        
        self.settings = settings
        
        # Initialize tools
        self.tools = []
        
        # Add time tool
        time_tool = TimeToolWrapper()
        self.tools.append(time_tool)
        
        # Initialize and add sub-assistant
        sub_assistant = OpenAIAssistant(
            name="writer_assistant",
            instructions="""Ты - специализированный ассистент, пишущий художественные тексты. Пиши красиво и выразительно.
            Всегда отвечай на русском языке, если не указано иное.""",
            model="gpt-4-turbo-preview",
            tools=[]  # Этот ассистент не использует инструменты
        )
        
        sub_assistant_tool = SubAssistantTool(
            sub_assistant=sub_assistant,
            name="writer",
            description="""Ассистент писатель. Используй его, когда нужно написать художественый текст.
            
            Примеры использования:
            - Написать красивое поздравление
            - Сочинить стихотворение
            - Написать креативное описание
            - Придумать интересную историю
            
            Параметры:
            - message: Текст запроса для писателя"""
        )
        self.tools.append(sub_assistant_tool)

        reminder_tool = ReminderTool()
        self.tools.append(reminder_tool)
        
        # Initialize main assistant
        self.assistant = OpenAIAssistant(
            instructions=ASSISTANT_INSTRUCTIONS,
            name="secretary",
            model="gpt-4-turbo-preview",
            tools=[tool.openai_schema for tool in self.tools],
            tool_instances=self.tools
        )
        
        logger.info("Assistant service initialized",
                   tool_count=len(self.tools))
    
    async def process_message(self, message: dict) -> dict:
        """Process an incoming message."""
        try:
            user_id = str(message.get("user_id", ""))
            chat_id = str(message.get("chat_id", ""))
            text = message["message"]
            
            logger.info("Processing message",
                       user_id=user_id,
                       chat_id=chat_id,
                       message_length=len(text))
            
            response = await self.assistant.process_message(text, user_id)
            
            return {
                "user_id": user_id,
                "chat_id": chat_id,
                "status": "success",
                "response": response
            }
            
        except Exception as e:
            logger.error("Message processing failed",
                        error=str(e),
                        exc_info=True)
            return {
                "user_id": message.get("user_id", ""),
                "chat_id": message.get("chat_id", ""),
                "status": "error",
                "error": str(e)
            }
    
    async def listen_for_messages(self):
        """Listen for messages from Redis queue."""
        while True:
            try:
                # Get message from input queue
                message = await self.redis.brpop(self.settings.INPUT_QUEUE, timeout=0)
                message_data = json.loads(message[1])
                
                # Process message
                result = await self.process_message(message_data)
                
                # Send result to output queue
                await self.redis.rpush(self.settings.OUTPUT_QUEUE, json.dumps(result))
                
            except Exception as e:
                logger.error("Message processing failed",
                           error=str(e),
                           exc_info=True)

async def main():
    """Main entry point."""
    try:
        service = AssistantOrchestrator()
        await service.listen_for_messages()
    except Exception as e:
        logger.error("Service failed",
                    error=str(e),
                    exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 