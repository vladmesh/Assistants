from typing import List, Dict, Any
import os
from langchain.agents.openai_assistant import OpenAIAssistantRunnable
from langchain.tools import BaseTool
import json
from config.logger import get_logger
from utils.retry import with_retry
from utils.error_handler import (
    handle_error,
    AssistantError,
    ToolError,
    ModelError,
    RateLimitError,
    is_retryable_error
)

logger = get_logger(__name__)

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
        self.name = name
        self.model = model
        
        # Convert LangChain tools to OpenAI format
        openai_tools = [tool.openai_schema for tool in tools]
        
        logger.info("Creating assistant",
                   name=name,
                   model=model,
                   tools_count=len(tools),
                   tools=[tool.name for tool in tools])
        
        self.assistant = OpenAIAssistantRunnable.create_assistant(
            name=name,
            instructions=instructions,
            tools=openai_tools,
            model=model
        )
        logger.info("Assistant created successfully", name=name)
    
    async def _invoke_assistant(self, message: str, thread_context: Dict[str, Any]) -> List[Any]:
        """Invoke the assistant with retry mechanism"""
        return await with_retry(
            self.assistant.ainvoke,
            {"content": message, "thread": thread_context},
            max_attempts=3,
            delay=1.0,
            backoff=2.0,
            exceptions=(RateLimitError, ConnectionError, TimeoutError),
            context={"assistant_name": self.name, "model": self.model}
        )
    
    async def _execute_tool(self, tool: BaseTool, args: Dict[str, Any]) -> str:
        """Execute a tool with retry mechanism"""
        return await with_retry(
            tool._arun,
            **args,
            max_attempts=2,
            delay=0.5,
            backoff=1.5,
            exceptions=(ConnectionError, TimeoutError),
            context={"assistant_name": self.name, "tool_name": tool.name}
        )
    
    async def process_message(self, user_message: str, user_id: str = None, chat_id: str = None) -> Dict[str, Any]:
        """Process a user message and return the response."""
        try:
            logger.info("Processing message",
                       assistant_name=self.name,
                       user_id=user_id,
                       chat_id=chat_id,
                       message_length=len(user_message),
                       message_preview=user_message[:100] + "..." if len(user_message) > 100 else user_message)
            
            # Create thread context
            thread_context = {"user_id": user_id, "chat_id": chat_id} if user_id and chat_id else None
            
            # Invoke assistant with retry
            try:
                response = await self._invoke_assistant(user_message, thread_context)
            except Exception as e:
                if is_retryable_error(e):
                    raise ModelError(
                        message="Ошибка при обращении к модели",
                        error_code="MODEL_ERROR",
                        details={"original_error": str(e)}
                    )
                raise
            
            logger.info("Got initial response",
                       assistant_name=self.name,
                       response_type=type(response[0]).__name__ if response else None)
            
            # Extract response text or handle tool calls
            if response and len(response) > 0:
                assistant_message = response[0]
                
                # Handle tool calls
                if hasattr(assistant_message, 'function'):
                    logger.info("Handling tool call",
                              assistant_name=self.name,
                              tool_name=assistant_message.function.name,
                              arguments=assistant_message.function.arguments)
                    
                    # Find the tool
                    tool_name = assistant_message.function.name
                    tool = next((t for t in self.tools if t.name == tool_name), None)
                    
                    if not tool:
                        raise ToolError(
                            message=f"Инструмент {tool_name} не найден",
                            error_code="TOOL_NOT_FOUND",
                            details={"available_tools": [t.name for t in self.tools]}
                        )
                    
                    # Parse arguments and run the tool
                    try:
                        args = json.loads(assistant_message.function.arguments)
                        # Добавляем user_id из контекста
                        if thread_context and "user_id" in thread_context:
                            args["user_id"] = thread_context["user_id"]
                    except json.JSONDecodeError as e:
                        raise ValidationError(
                            message="Неверный формат аргументов инструмента",
                            error_code="INVALID_TOOL_ARGS",
                            details={"original_error": str(e)}
                        )
                    
                    logger.info("Running tool",
                              assistant_name=self.name,
                              tool_name=tool_name,
                              arguments=args)
                              
                    try:
                        tool_response = await self._execute_tool(tool, args)
                    except Exception as e:
                        if is_retryable_error(e):
                            raise ToolError(
                                message=f"Ошибка при выполнении инструмента {tool_name}",
                                error_code="TOOL_EXECUTION_ERROR",
                                details={"original_error": str(e)}
                            )
                        raise
                    
                    logger.info("Tool execution completed",
                              assistant_name=self.name,
                              tool_name=tool_name,
                              response_length=len(str(tool_response)))
                    
                    # Submit tool output back to assistant
                    logger.info("Submitting tool response back to assistant",
                              assistant_name=self.name,
                              tool_name=tool_name)
                              
                    try:
                        final_response = await self._invoke_assistant(tool_response, thread_context)
                    except Exception as e:
                        if is_retryable_error(e):
                            raise ModelError(
                                message="Ошибка при обработке ответа инструмента",
                                error_code="MODEL_ERROR",
                                details={"original_error": str(e)}
                            )
                        raise
                    
                    logger.info("Got final response after tool call",
                              assistant_name=self.name,
                              tool_name=tool_name,
                              response_type=type(final_response[0]).__name__ if final_response else None)
                    
                    if final_response and len(final_response) > 0:
                        final_message = final_response[0]
                        
                        if hasattr(final_message, 'content') and final_message.content:
                            response_text = final_message.content[0].text.value
                            logger.info("Successfully processed tool response",
                                      assistant_name=self.name,
                                      tool_name=tool_name,
                                      response_length=len(response_text))
                            return {
                                "status": "success",
                                "response": response_text,
                                "error": None
                            }
                        else:
                            raise ModelError(
                                message="Неверный формат ответа от модели",
                                error_code="INVALID_MODEL_RESPONSE",
                                details={"message_type": type(final_message).__name__}
                            )
                
                # Handle direct text responses
                elif hasattr(assistant_message, 'content') and assistant_message.content:
                    response_text = assistant_message.content[0].text.value
                    logger.info("Processing direct text response",
                              assistant_name=self.name,
                              response_length=len(response_text))
                    return {
                        "status": "success",
                        "response": response_text,
                        "error": None
                    }
                else:
                    raise ModelError(
                        message="Ответ не содержит ни текста, ни вызова инструмента",
                        error_code="INVALID_MODEL_RESPONSE",
                        details={"message_type": type(assistant_message).__name__}
                    )
            else:
                raise ModelError(
                    message="Получен пустой ответ от модели",
                    error_code="EMPTY_MODEL_RESPONSE"
                )
                
        except Exception as e:
            return handle_error(e, {
                "assistant_name": self.name,
                "user_id": user_id,
                "chat_id": chat_id,
                "message_length": len(user_message)
            }) 