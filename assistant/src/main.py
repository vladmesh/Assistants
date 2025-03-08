import os
import json
import asyncio
from typing import Dict, Any
import redis.asyncio as redis
from dotenv import load_dotenv

from models.assistant import Assistant
from tools.calendar_tool import CalendarTool

# Load environment variables
load_dotenv()

class AssistantOrchestrator:
    def __init__(self):
        self.redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True
        )
        
        # Initialize tools
        self.tools = [
            CalendarTool(),
            # Add more tools here as needed
        ]
        
        # Initialize assistant
        self.assistant = Assistant(
            tools=self.tools,
            name="Секретарь",
            instructions="""Ты - умный секретарь, который помогает пользователю управлять различными аспектами жизни.
            Твои основные задачи:
            1. Управление календарем (создание, изменение, удаление встреч)
            2. Ответы на вопросы пользователя
            3. Помощь в планировании дня
            
            Всегда отвечай на русском языке.
            Будь точным с датами и временем.
            Если не уверен в чем-то - переспроси у пользователя."""
        )
    
    async def process_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message and return the response."""
        try:
            result = await self.assistant.process_message(
                message=data["message"],
                user_id=data["user_id"],
                chat_id=data.get("chat_id")
            )
            return {
                "user_id": data["user_id"],
                "chat_id": data.get("chat_id"),
                **result
            }
        except Exception as e:
            return {
                "user_id": data["user_id"],
                "chat_id": data.get("chat_id"),
                "status": "error",
                "response": None,
                "error": str(e)
            }
    
    async def listen_for_messages(self):
        """Listen for messages in the Redis queue."""
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
                print(f"Error processing message: {e}")
                continue

async def main():
    orchestrator = AssistantOrchestrator()
    await orchestrator.listen_for_messages()

if __name__ == "__main__":
    asyncio.run(main()) 