from typing import ClassVar, Optional

from assistants.llm_chat import BaseLLMChat
from config.logger import get_logger
from langchain.schema import HumanMessage
from tools.base import BaseTool, SubAssistantSchema

logger = get_logger(__name__)


class SubAssistantTool(BaseTool):
    """Tool wrapper for BaseLLMChat."""

    NAME: ClassVar[str] = "sub_assistant"
    DESCRIPTION: ClassVar[str] = (
        "Инструмент для делегирования задач специализированному ассистенту.\n"
        "Используйте его, когда нужно выполнить специфическую задачу,\n"
        "требующую глубокого понимания контекста.\n"
        "\n"
        "Примеры использования:\n"
        "- Анализ сложных текстов\n"
        "- Генерация специализированного контента\n"
        "- Решение узкоспециализированных задач\n"
        "\n"
        "Параметры:\n"
        "- message: Текст запроса для специализированного ассистента\n"
    )

    name: str = NAME
    description: str = DESCRIPTION
    tool_type: str = "sub_assistant"
    sub_assistant: Optional[BaseLLMChat] = None
    assistant_id: Optional[str] = None

    def __init__(
        self,
        sub_assistant: BaseLLMChat,
        assistant_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Initialize the tool with a sub-assistant.

        Args:
            sub_assistant: The specialized assistant to delegate tasks to
            assistant_id: ID of the assistant in the database
            name: Optional custom name for the tool
            description: Optional custom description
            user_id: Optional user identifier
        """
        super().__init__(
            name=name or self.NAME,
            description=description or self.DESCRIPTION,
            args_schema=SubAssistantSchema,
            user_id=user_id,
        )
        self.sub_assistant = sub_assistant
        self.assistant_id = assistant_id

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
        try:
            if not self.sub_assistant:
                logger.error(
                    "Sub-assistant is not initialized",
                    tool_name=self.name,
                    assistant_id=self.assistant_id,
                )
                raise ValueError("Sub-assistant is not initialized")

            logger.info(
                "Delegating request to sub-assistant",
                message=message,
                assistant_name=self.sub_assistant.name,
                tool_name=self.name,
                user_id=self.user_id,
                assistant_id=self.assistant_id,
            )

            try:
                logger.debug(
                    "Creating HumanMessage",
                    message=message,
                    tool_name=self.name,
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
                    assistant_name=self.sub_assistant.name,
                    tool_name=self.name,
                )
                logger.debug(
                    "Calling process_message on sub-assistant",
                    message=message,
                    assistant_name=self.sub_assistant.name,
                    tool_name=self.name,
                    user_id=self.user_id,
                )
                response = await self.sub_assistant.process_message(
                    human_message, self.user_id
                )
                logger.debug(
                    "process_message completed successfully",
                    assistant_name=self.sub_assistant.name,
                    tool_name=self.name,
                )
                logger.info(
                    "Sub-assistant response received",
                    response=response,
                    assistant_name=self.sub_assistant.name,
                    tool_name=self.name,
                )
                return response
            except Exception as e:
                logger.error(
                    "Failed to process message with sub-assistant",
                    error=str(e),
                    error_type=type(e).__name__,
                    tool_name=self.name,
                    assistant_name=self.sub_assistant.name,
                    exc_info=True,
                )
                raise

        except Exception as e:
            logger.error(
                "Sub-assistant execution failed",
                error=str(e),
                error_type=type(e).__name__,
                tool_name=self.name,
                assistant_name=getattr(self.sub_assistant, "name", None),
                assistant_id=self.assistant_id,
                exc_info=True,
            )
            raise
