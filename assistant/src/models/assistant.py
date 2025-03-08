from typing import List, Dict, Any
import json
from datetime import datetime
import time
from openai import OpenAI
from openai.types.beta.threads import Run
from langchain.tools import BaseTool
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
from config.instructions import ASSISTANT_INSTRUCTIONS
from config.settings import settings

logger = get_logger(__name__)

class Assistant:
    def __init__(self):
        self.client = OpenAI()
        self.assistant_id = settings.OPEN_API_SECRETAR_ID
        self.name = "Секретарь"
        self.model = "gpt-4-1106-preview"
        self.tools = []
        
    def update_assistant(self, tools: List[BaseTool]):
        """Update the assistant with new instructions and tools."""
        self.tools = tools
        openai_tools = [tool.openai_schema for tool in tools]
        
        logger.info("Updating assistant",
                   name=self.name,
                   model=self.model,
                   tools_count=len(tools),
                   tools=[tool.name for tool in tools])
        
        try:
            self.client.beta.assistants.update(
                assistant_id=self.assistant_id,
                name=self.name,
                instructions=ASSISTANT_INSTRUCTIONS,
                tools=openai_tools,
                model=self.model
            )
            logger.info("Assistant updated successfully", name=self.name)
        except Exception as e:
            logger.error("Failed to update assistant", 
                        error=str(e),
                        assistant_id=self.assistant_id,
                        exc_info=True)
            raise
            
    async def _wait_for_run(self, thread_id: str, run_id: str) -> Run:
        """Wait for a run to complete and return the run object."""
        while True:
            run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.status == "completed":
                return run
            elif run.status == "requires_action":
                return run
            elif run.status in ["failed", "expired"]:
                raise ModelError(
                    message=f"Run failed with status: {run.status}",
                    error_code="RUN_FAILED",
                    details={"run_status": run.status}
                )
            time.sleep(0.5)
            
    async def _execute_tool(self, tool_call, thread_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        tool_name = tool_call.function.name
        tool = next((t for t in self.tools if t.name == tool_name), None)
        
        if not tool:
            raise ToolError(
                message=f"Инструмент {tool_name} не найден",
                error_code="TOOL_NOT_FOUND",
                details={"available_tools": [t.name for t in self.tools]}
            )
            
        try:
            args = json.loads(tool_call.function.arguments)
            if thread_context and "user_id" in thread_context:
                args["user_id"] = thread_context["user_id"]
        except json.JSONDecodeError as e:
            raise ToolError(
                message="Неверный формат аргументов инструмента",
                error_code="INVALID_TOOL_ARGS",
                details={"original_error": str(e)}
            )
            
        logger.info("Running tool",
                   tool_name=tool_name,
                   arguments=args)
                   
        try:
            result = await with_retry(
                tool._arun,
                **args,
                max_attempts=2,
                delay=0.5,
                backoff=1.5,
                exceptions=(ConnectionError, TimeoutError),
                context={"assistant_name": self.name, "tool_name": tool_name}
            )
            return {
                "tool_call_id": tool_call.id,
                "output": result
            }
        except Exception as e:
            if is_retryable_error(e):
                raise ToolError(
                    message=f"Ошибка при выполнении инструмента {tool_name}",
                    error_code="TOOL_EXECUTION_ERROR",
                    details={"original_error": str(e)}
                )
            raise
            
    async def process_message(self, user_message: str, user_id: str = None, chat_id: str = None) -> Dict[str, Any]:
        """Process a user message and return the response."""
        try:
            logger.info("Processing message",
                       assistant_name=self.name,
                       user_id=user_id,
                       chat_id=chat_id,
                       message_length=len(user_message))
                       
            # Create thread context
            thread_context = {
                "user_id": user_id,
                "chat_id": chat_id
            }
            
            # Add timestamp to message
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message_with_time = f"Текущее время: {current_time}\n\n{user_message}"
            
            # Create thread and add message
            thread = self.client.beta.threads.create()
            self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=message_with_time
            )
            
            # Start run
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            # Wait for completion or tool calls
            while True:
                run = await self._wait_for_run(thread.id, run.id)
                
                if run.status == "completed":
                    # Get messages
                    messages = self.client.beta.threads.messages.list(thread_id=thread.id)
                    assistant_message = next(msg for msg in messages if msg.role == "assistant")
                    
                    if not assistant_message.content:
                        raise ModelError(
                            message="Получен пустой ответ от модели",
                            error_code="EMPTY_MODEL_RESPONSE"
                        )
                        
                    response_text = assistant_message.content[0].text.value
                    return {
                        "status": "success",
                        "response": response_text,
                        "error": None
                    }
                    
                elif run.status == "requires_action":
                    # Handle tool calls
                    tool_outputs = []
                    for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                        tool_output = await self._execute_tool(tool_call, thread_context)
                        tool_outputs.append(tool_output)
                        
                    # Submit tool outputs
                    run = self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
                    
        except Exception as e:
            return handle_error(e, {
                "assistant_name": self.name,
                "user_id": user_id,
                "chat_id": chat_id,
                "message_length": len(user_message)
            }) 