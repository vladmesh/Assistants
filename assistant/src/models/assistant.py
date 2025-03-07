from typing import List, Dict, Any
import os
import logging
from langchain.agents.openai_assistant import OpenAIAssistantRunnable
from langchain.tools import BaseTool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Assistant:
    def __init__(
        self,
        tools: List[BaseTool],
        name: str = "Секретарь",
        instructions: str = """Ты - умный секретарь, который помогает пользователю управлять различными аспектами жизни.
        Твои основные задачи:
        1. Управление календарем (создание, изменение, удаление встреч)
        2. Ответы на вопросы пользователя
        3. Помощь в планировании дня
        
        Всегда отвечай на русском языке.
        Будь точным с датами и временем.
        Если не уверен в чем-то - переспроси у пользователя.
        """,
        model: str = "gpt-4-1106-preview"
    ):
        self.tools = tools
        
        # Convert LangChain tools to OpenAI format
        openai_tools = [tool.openai_schema for tool in tools]
        
        logger.info(f"Creating assistant with {len(tools)} tools")
        self.assistant = OpenAIAssistantRunnable.create_assistant(
            name=name,
            instructions=instructions,
            tools=openai_tools,
            model=model
        )
        logger.info(f"Assistant created successfully")
    
    async def process_message(self, message: str, user_id: str = None, chat_id: str = None) -> Dict[str, Any]:
        """Process a user message and return the response."""
        try:
            logger.info(f"Processing message from user {user_id}: {message}")
            
            # Use thread_id based on user_id and chat_id to maintain context
            thread = {"user_id": user_id, "chat_id": chat_id} if user_id and chat_id else None
            
            response = await self.assistant.ainvoke({
                "content": message,
                "thread": thread
            })
            
            logger.info(f"Got response: {response}")
            return {
                "status": "success",
                "response": response["output"],
                "error": None
            }
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                "status": "error",
                "response": None,
                "error": str(e)
            } 