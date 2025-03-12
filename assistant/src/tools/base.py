"""Base classes for tools"""
from typing import Any, Optional, Dict, Type
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool as LangBaseTool
from pydantic import BaseModel, Field, ValidationError
from assistants.base import BaseAssistant
from utils.error_handler import ToolError, ToolExecutionError, InvalidInputError

class MessageInput(BaseModel):
    """Schema for message input to assistants"""
    message: str = Field(description="A request to LLM containing the message to be processed")

class BaseTool(LangBaseTool):
    """Base class for assistant tools"""
    def __init__(
            self,
            name: str,
            description: str,
            args_schema: Optional[BaseModel] = None,
            user_id: Optional[str] = None,
            **kwargs
    ):
        """Initialize the tool

        Args:
            name: The name of the tool
            description: A description of what the tool does
            args_schema: Optional schema for the function arguments
            user_id: Optional user identifier for tool context

        Raises:
            ToolError: If initialization fails
        """
        try:
            super().__init__(
                name=name,
                description=description,
                args_schema=args_schema,
                **kwargs
            )
            self._user_id = user_id
        except Exception as e:
            raise ToolError(f"Failed to initialize tool: {str(e)}", name)

    @property
    def user_id(self) -> Optional[str]:
        """Get the user ID associated with this tool instance"""
        return self._user_id

    @user_id.setter
    def user_id(self, value: str):
        """Set the user ID for this tool instance"""
        self._user_id = value

    @property
    def openai_schema(self) -> Dict[str, Any]:
        """Get OpenAI function schema for the tool"""
        schema = self.args_schema.model_json_schema() if self.args_schema else {}
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema
            }
        }

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool asynchronously
        
        Raises:
            ToolExecutionError: If execution fails
        """
        try:
            result = await self._execute(*args, **kwargs)
            return result
        except ValidationError as e:
            raise InvalidInputError(f"Invalid input: {str(e)}")
        except Exception as e:
            raise ToolExecutionError(f"Tool execution failed: {str(e)}", self.name)

    async def _execute(self, *args: Any, **kwargs: Any) -> Any:
        """Actual tool execution logic to be implemented by subclasses"""
        raise NotImplementedError(
            "You need to implement _execute method"
        )

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool synchronously - not supported"""
        raise NotImplementedError(
            "Synchronous execution is not supported, use _arun instead"
        )

class ToolAssistant(BaseTool):
    """Tool that wraps an assistant to be used by other assistants"""
    assistant: BaseAssistant = Field(description="Assistant instance to process messages")
    
    def __init__(self, name: str, description: str, assistant: BaseAssistant, **kwargs):
        # If args_schema is not provided, use MessageInput as default
        if 'args_schema' not in kwargs:
            kwargs['args_schema'] = MessageInput
            
        try:
            super().__init__(
                name=name,
                description=description,
                assistant=assistant,
                **kwargs
            )
        except Exception as e:
            raise ToolError(f"Failed to initialize tool assistant: {str(e)}", name)

    async def _execute(self, message: str, user_id=None):
        """Process message through the wrapped assistant"""
        try:
            return await self.assistant.process_message(message)
        except Exception as e:
            raise ToolExecutionError(f"Assistant execution failed: {str(e)}", self.name)

class SubAssistantSchema(BaseModel):
    """Base schema for all sub-assistant based tools."""
    message: str = Field(..., description="Запрос для LLM в виде текста")
