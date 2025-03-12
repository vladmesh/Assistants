from typing import Optional, Type, ClassVar
from tools.base import BaseTool, SubAssistantSchema
from assistants.sub_assistant import SubAssistant
from config.logger import get_logger

logger = get_logger(__name__)

class SubAssistantTool(BaseTool):
    """Tool wrapper for SubAssistant."""
    NAME: ClassVar[str] = "sub_assistant"
    DESCRIPTION: ClassVar[str] = """Инструмент для делегирования задач специализированному ассистенту.
    Используйте его, когда нужно выполнить специфическую задачу, требующую глубокого понимания контекста.
    
    Примеры использования:
    - Анализ сложных текстов
    - Генерация специализированного контента
    - Решение узкоспециализированных задач
    
    Параметры:
    - message: Текст запроса для специализированного ассистента
    """
    
    name: str = NAME
    description: str = DESCRIPTION
    sub_assistant: Optional[SubAssistant] = None
    
    def __init__(
        self,
        sub_assistant: SubAssistant,
        name: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Initialize the tool with a sub-assistant.
        
        Args:
            sub_assistant: The specialized assistant to delegate tasks to
            name: Optional custom name for the tool
            description: Optional custom description
            user_id: Optional user identifier
        """
        super().__init__(
            name=name or self.NAME,
            description=description or self.DESCRIPTION,
            args_schema=SubAssistantSchema,
            user_id=user_id
        )
        self.sub_assistant = sub_assistant
    
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
            raise ValueError("Sub-assistant is not initialized")
            
        logger.info("Delegating request to sub-assistant",
                   message=message,
                   assistant_name=self.sub_assistant.name)
        
        try:
            response = await self.sub_assistant.process_message(message, self.user_id)
            return response
        except Exception as e:
            logger.error("Sub-assistant execution failed",
                        error=str(e),
                        exc_info=True)
            raise 