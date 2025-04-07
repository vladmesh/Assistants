from typing import Optional

from assistants.base_assistant import BaseAssistant
from config.logger import get_logger
from config.settings import Settings
from langchain.schema import HumanMessage
from tools.base import BaseTool, SubAssistantSchema

logger = get_logger(__name__)


class SubAssistantTool(BaseTool):
    """Tool wrapper for BaseLLMChat."""

    # NAME and DESCRIPTION removed - they come from the database via ToolFactory
    # NAME: ClassVar[str] = "sub_assistant"
    # DESCRIPTION: ClassVar[str] = (
    #     "Инструмент для делегирования задач специализированному ассистенту.\n"
    #     "Используйте его, когда нужно выполнить специфическую задачу,\n"
    #     "требующую глубокого понимания контекста.\n"
    #     "\n"
    #     "Примеры использования:\n"
    #     "- Анализ сложных текстов\n"
    #     "- Генерация специализированного контента\n"
    #     "- Решение узкоспециализированных задач\n"
    #     "\n"
    #     "Параметры:\n"
    #     "- message: Текст запроса для специализированного ассистента\n"
    # )

    # Keep args_schema as a class attribute for Langchain
    args_schema: type[SubAssistantSchema] = SubAssistantSchema
    sub_assistant: BaseAssistant
    sub_assistant_db_id: Optional[str] = None

    def __init__(
        self,
        sub_assistant: BaseAssistant,
        settings: Settings,
        user_id: str,
        parent_assistant_id: str,
        sub_assistant_db_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Initialize the tool with a sub-assistant.

        Args:
            sub_assistant: The specialized assistant to delegate tasks to.
            settings: Application settings.
            user_id: User identifier.
            parent_assistant_id: ID of the assistant this tool belongs to.
            sub_assistant_db_id: The database ID of the sub-assistant being wrapped.
            tool_id: The database ID of this tool instance.
            name: Optional custom name for the tool.
            description: Optional custom description.
        """
        # Initialize BaseTool. args_schema is handled by the class attribute.
        super().__init__(
            name=name or self.name,
            description=description or self.description,
            settings=settings,
            user_id=user_id,
            assistant_id=parent_assistant_id,
            tool_id=tool_id,
        )
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
                logger.debug(
                    "Creating HumanMessage", message=message, tool_name=self.name
                )
                human_message = HumanMessage(content=message)
                logger.debug(
                    "HumanMessage created",
                    message=str(human_message),
                    tool_name=self.name,
                )
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
                logger.debug(
                    "Processing message with sub-assistant",
                    message=message,
                    sub_assistant_name=self.sub_assistant.name,
                    user_id=self.user_id,
                    tool_name=self.name,
                )
                response = await self.sub_assistant.process_message(
                    human_message, self.user_id
                )
                logger.debug(
                    "process_message completed successfully",
                    sub_assistant_name=self.sub_assistant.name,
                    tool_name=self.name,
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
