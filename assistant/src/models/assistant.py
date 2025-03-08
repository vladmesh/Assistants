from typing import List, Dict, Any
import os
import logging
from langchain.agents.openai_assistant import OpenAIAssistantRunnable
from langchain.tools import BaseTool
import json

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
            
            # Create thread context
            thread_context = {"user_id": user_id, "chat_id": chat_id} if user_id and chat_id else None
            
            # Invoke assistant
            logger.info("Invoking assistant...")
            response = await self.assistant.ainvoke({
                "content": message,
                "thread": thread_context
            })
            
            logger.info(f"Got initial response: {response}")
            
            # Extract response text or handle tool calls
            if response and len(response) > 0:
                message = response[0]
                logger.info(f"Processing message type: {type(message)}")
                
                # Handle tool calls
                if hasattr(message, 'function'):
                    logger.info(f"Handling tool call for {message.function.name}")
                    # Find the tool
                    tool_name = message.function.name
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    
                    if not tool:
                        raise RuntimeError(f"Tool {tool_name} not found")
                    
                    # Parse arguments and run the tool
                    args = json.loads(message.function.arguments)
                    logger.info(f"Running tool {tool_name} with args: {args}")
                    tool_response = await tool._arun(**args)
                    logger.info(f"Tool response: {tool_response}")
                    
                    # Submit tool output back to assistant
                    logger.info("Submitting tool response back to assistant...")
                    final_response = await self.assistant.ainvoke({
                        "content": tool_response,
                        "thread": thread_context
                    })
                    
                    logger.info(f"Final response after tool call: {final_response}")
                    
                    if final_response and len(final_response) > 0:
                        final_message = final_response[0]
                        logger.info(f"Final message type: {type(final_message)}")
                        
                        if hasattr(final_message, 'content') and final_message.content:
                            return {
                                "status": "success",
                                "response": final_message.content[0].text.value,
                                "error": None
                            }
                        else:
                            logger.error(f"Unexpected final message format: {final_message}")
                
                # Handle direct text responses
                elif hasattr(message, 'content') and message.content:
                    logger.info("Processing direct text response")
                    return {
                        "status": "success",
                        "response": message.content[0].text.value,
                        "error": None
                    }
                else:
                    logger.error(f"Message has no content or function: {message}")
            else:
                logger.error("Empty response from assistant")
            
            return {
                "status": "error",
                "response": None,
                "error": "Не получен ответ от ассистента"
            }
                
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "response": None,
                "error": str(e)
            } 