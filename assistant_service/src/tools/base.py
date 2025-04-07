"""Base classes for tools"""

import logging
from typing import Any, Dict, Optional, Type

from assistants.base_assistant import BaseAssistant
from config.settings import Settings
from langchain_core.tools import BaseTool as LangBaseTool
from pydantic import BaseModel, Field, ValidationError
from utils.error_handler import InvalidInputError, ToolError, ToolExecutionError

logger = logging.getLogger(__name__)


class MessageInput(BaseModel):
    """Schema for message input to assistants"""

    message: str = Field(
        description="A request to LLM containing the message to be processed"
    )


class BaseTool(LangBaseTool):
    """Custom base class for tools with settings and user context."""

    # Add common fields expected by our framework
    settings: Optional[Settings] = None
    user_id: Optional[str] = None
    assistant_id: Optional[str] = None
    tool_id: Optional[str] = None

    # Allow arbitrary types for flexibility, though specific tools might constrain this
    args_schema: Optional[Type[BaseModel]] = None

    class Config:
        # Allow arbitrary types to be stored on the model
        arbitrary_types_allowed = True

    def __init__(
        self,
        name: str,
        description: str,
        settings: Optional[Settings] = None,
        user_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        args_schema: Optional[
            Type[BaseModel]
        ] = None,  # Keep param for ToolFactory compatibility
        **kwargs,  # Catch any other args passed by ToolFactory
    ):
        """Initialize the tool

        Args:
            name: The name of the tool
            description: A description of what the tool does
            settings: Optional settings for the tool
            user_id: Optional user identifier for tool context
            assistant_id: Optional assistant identifier for tool context
            tool_id: Optional tool identifier for tool context
            args_schema: Optional schema for the function arguments (Ignored in super call)

        Raises:
            ToolError: If initialization fails
        """
        try:
            # Initialize the Langchain BaseTool first.
            # Do NOT pass args_schema here; let Langchain find the class attribute.
            super().__init__(name=name, description=description, **kwargs)

            # Store our custom attributes
            self.settings = settings
            self.user_id = user_id
            self.assistant_id = assistant_id
            self.tool_id = tool_id
            # We still store the args_schema passed from ToolFactory if any,
            # but it's not directly used by Langchain BaseTool init anymore.
            # Langchain should pick up the class attribute args_schema from the child tool class.
            if args_schema:
                self.args_schema = args_schema
            # If not passed, rely on the class attribute defined in the child class
            elif not hasattr(self, "args_schema") or self.args_schema is None:
                # Attempt to get it from the class definition if it exists
                if hasattr(self.__class__, "args_schema"):
                    self.args_schema = getattr(self.__class__, "args_schema", None)
                else:
                    # If still no schema, maybe log a warning or set a default?
                    logger.warning(f"Tool '{name}' initialized without an args_schema.")
                    self.args_schema = None

        except Exception as e:
            # Log the actual error during initialization
            logger.error(f"Failed to initialize tool '{name}': {str(e)}", exc_info=True)
            # Raise a more specific error
            raise ToolError(f"Failed to initialize tool: {str(e)}", name) from e

    @property
    def openai_schema(self) -> Dict[str, Any]:
        """Get OpenAI function schema for the tool"""
        schema = self.args_schema.model_json_schema() if self.args_schema else {}

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
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
            f"{self.name} tool must implement the async _execute method"
        )

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool synchronously - not supported"""
        raise NotImplementedError(f"{self.name} tool does not support sync execution")


class ToolAssistant(BaseTool):
    """Tool that wraps an assistant to be used by other assistants"""

    assistant: BaseAssistant = Field(
        description="Assistant instance to process messages"
    )

    def __init__(self, name: str, description: str, assistant: BaseAssistant, **kwargs):
        # If args_schema is not provided, use MessageInput as default
        if "args_schema" not in kwargs:
            kwargs["args_schema"] = MessageInput

        try:
            super().__init__(
                name=name, description=description, assistant=assistant, **kwargs
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
