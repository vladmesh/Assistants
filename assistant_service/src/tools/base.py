"""Base classes for tools"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.tools import BaseTool as LangBaseTool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from config.settings import Settings
from utils.error_handler import InvalidInputError, ToolError, ToolExecutionError

if TYPE_CHECKING:
    from assistants.base_assistant import BaseAssistant

logger = logging.getLogger(__name__)


class MessageInput(BaseModel):
    """Schema for message input to assistants"""

    message: str = Field(
        description="A request to LLM containing the message to be processed"
    )


class BaseTool(LangBaseTool):
    """Custom base class for tools with settings and user context."""

    # Add common fields expected by our framework
    settings: Settings | None = None
    user_id: str | None = None
    assistant_id: str | None = None
    tool_id: str | None = None

    # Allow arbitrary types for flexibility, though specific tools might constrain this
    args_schema: type[BaseModel] | None = None

    model_config = ConfigDict(
        # Allow arbitrary types to be stored on the model
        arbitrary_types_allowed=True
    )

    def __init__(
        self,
        name: str,
        description: str,
        settings: Settings | None = None,
        user_id: str | None = None,
        assistant_id: str | None = None,
        tool_id: str | None = None,
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

        Raises:
            ToolError: If initialization fails
        """
        try:
            # Initialize the Langchain BaseTool first.
            # args_schema is NOT passed here; Langchain uses the class attribute.
            super().__init__(name=name, description=description, **kwargs)

            # Store our custom attributes
            self.settings = settings
            self.user_id = user_id
            self.assistant_id = assistant_id
            self.tool_id = tool_id

            # Check if the class itself has args_schema defined
            if (
                not hasattr(self.__class__, "args_schema")
                or getattr(self.__class__, "args_schema", None) is None
            ):
                logger.warning(
                    f"Tool class '{self.__class__.__name__}' (name='{name}') "
                    "is defined without args_schema."
                )

        except Exception as e:
            # Log the actual error during initialization
            logger.error(f"Failed to initialize tool '{name}': {str(e)}", exc_info=True)
            # Raise a more specific error
            raise ToolError(f"Failed to initialize tool: {str(e)}", name) from e

    @property
    def openai_schema(self) -> dict[str, Any]:
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
            raise InvalidInputError(f"Invalid input: {str(e)}") from e
        except Exception as e:
            raise ToolExecutionError(
                f"Tool execution failed: {str(e)}", self.name
            ) from e

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
            raise ToolError(
                f"Failed to initialize tool assistant: {str(e)}", name
            ) from e

    async def _execute(self, message: str, user_id=None):
        """Process message through the wrapped assistant"""
        try:
            return await self.assistant.process_message(message)
        except Exception as e:
            raise ToolExecutionError(
                f"Assistant execution failed: {str(e)}", self.name
            ) from e


class SubAssistantSchema(BaseModel):
    """Base schema for all sub-assistant based tools."""

    message: str = Field(..., description="Запрос для LLM в виде текста")
