from typing import Any

from langchain.schema import HumanMessage

from assistants.base_assistant import BaseAssistant
from config.logger import get_logger
from config.settings import Settings
from tools.base import BaseTool, SubAssistantSchema

logger = get_logger(__name__)


class SubAssistantTool(BaseTool):
    """Tool wrapper for BaseLLMChat."""

    # Keep args_schema as a class attribute for Langchain
    args_schema: type[SubAssistantSchema] = SubAssistantSchema
    # Revert sub_assistant to simple type hint
    sub_assistant: BaseAssistant
    sub_assistant_db_id: str | None = None

    # Restore original __init__ signature
    def __init__(
        self,
        sub_assistant: BaseAssistant,
        settings: Settings,
        user_id: str,
        parent_assistant_id: str,
        sub_assistant_db_id: str | None = None,
        tool_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        **kwargs: Any,  # Add kwargs to catch anything extra
    ):
        """Initialize the tool with a sub-assistant.

        Args:
            sub_assistant: The specialized assistant to delegate tasks to.
            settings: The settings for the tool.
            user_id: The ID of the user.
            parent_assistant_id: The ID of the parent assistant.
            sub_assistant_db_id: The database ID of the sub-assistant.
            tool_id: The ID of the tool.
            name: The name of the tool.
            description: The description of the tool.
            **kwargs: Additional keyword arguments.
        """
        # Call BaseTool's __init__ first
        super().__init__(
            name=name or self.name,  # Use provided or class name
            description=description
            or self.description,  # Use provided or class description
            settings=settings,
            user_id=user_id,
            assistant_id=parent_assistant_id,  # This is the parent's ID
            tool_id=tool_id,
            # Pass sub_assistant in kwargs for potential BaseTool/Pydantic processing
            sub_assistant=sub_assistant,
            **kwargs,  # Pass any other unexpected kwargs up
        )
        # Explicitly set the attribute AFTER super().__init__
        self.sub_assistant = sub_assistant
        self.sub_assistant_db_id = sub_assistant_db_id

    def _run(self, message: str) -> str:
        """Synchronous execution is not supported."""
        raise NotImplementedError("This tool only supports async execution")

    async def _execute(self, message: str) -> str:
        """Execute the request using the sub-assistant.

        Args:
            message: The request text for the sub-assistant

        Returns:
            The sub-assistant's response

        Raises:
            ToolError: If execution fails
        """
        if not self.sub_assistant:
            logger.error(
                "Sub-assistant is not initialized during execution",
                tool_name=self.name,
                sub_assistant_db_id=self.sub_assistant_db_id,
                parent_assistant_id=self.assistant_id,
            )
            raise ValueError("Sub-assistant is not initialized")

        try:
            logger.info(
                "Delegating request to sub-assistant",
                message=message,
                sub_assistant_name=self.sub_assistant.name,
                sub_assistant_db_id=self.sub_assistant_db_id,
                tool_name=self.name,
                user_id=self.user_id,
                parent_assistant_id=self.assistant_id,
            )

            try:
                human_message = HumanMessage(content=message)
            except Exception as e:
                logger.error(
                    "Failed to create HumanMessage",
                    error=str(e),
                    error_type=type(e).__name__,
                    tool_name=self.name,
                    exc_info=True,
                )
                raise

            try:
                response = await self.sub_assistant.process_message(
                    human_message, self.user_id
                )
                logger.info(
                    "Sub-assistant response received",
                    response=response,
                    sub_assistant_name=self.sub_assistant.name,
                    tool_name=self.name,
                )
                return response
            except Exception as e:
                logger.error(
                    "Failed to process message with sub-assistant",
                    error=str(e),
                    error_type=type(e).__name__,
                    tool_name=self.name,
                    sub_assistant_name=self.sub_assistant.name,
                    exc_info=True,
                )
                raise

        except Exception as e:
            logger.error(
                "Sub-assistant tool execution failed",
                error=str(e),
                error_type=type(e).__name__,
                tool_name=self.name,
                sub_assistant_name=getattr(self.sub_assistant, "name", None),
                sub_assistant_db_id=self.sub_assistant_db_id,
                parent_assistant_id=self.assistant_id,
                exc_info=True,
            )
            raise
