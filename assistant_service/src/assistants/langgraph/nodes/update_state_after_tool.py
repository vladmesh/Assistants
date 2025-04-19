import logging
from typing import Any, Dict

from assistants.langgraph.state import AssistantState
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

# Имя инструмента, после которого нужно обновить флаг
# Должно совпадать с `name`, присвоенным UserFactTool в ToolFactory
USER_FACT_TOOL_NAME = "save_user_fact"
# Ожидаемое (успешное) сообщение от UserFactTool
USER_FACT_SUCCESS_MESSAGE = "Факт успешно добавлен."


async def update_state_after_tool_node(state: AssistantState) -> Dict[str, Any]:
    """
    Checks the last message after a tool call. If it's a successful
    ToolMessage from UserFactTool, sets the fact_added_in_last_run flag.

    Reads from state:
        - messages: The current list of messages.

    Updates state:
        - fact_added_in_last_run: Set to True if UserFactTool was successful.
    """
    messages = state.get("messages", [])
    user_id = state.get("user_id", "unknown")
    log_extra = {"user_id": user_id}
    update = {}

    if messages and isinstance(messages[-1], ToolMessage):
        last_tool_message = messages[-1]
        tool_name = getattr(last_tool_message, "name", None)
        tool_content = last_tool_message.content

        logger.debug(
            f"Checking last ToolMessage: name='{tool_name}', content='{tool_content[:50]}...'",
            extra=log_extra,
        )

        # Проверяем имя инструмента и успешное сообщение
        if (
            tool_name == USER_FACT_TOOL_NAME
            and tool_content == USER_FACT_SUCCESS_MESSAGE
        ):
            logger.info(
                f"Detected successful execution of {USER_FACT_TOOL_NAME}. Setting fact_added_in_last_run=True.",
                extra=log_extra,
            )
            update["fact_added_in_last_run"] = True
        else:
            # Если был вызван другой инструмент или UserFactTool вернул ошибку,
            # убедимся, что флаг сброшен (хотя check_facts его тоже сбрасывает)
            update["fact_added_in_last_run"] = False
    else:
        # Последнее сообщение не ToolMessage, флаг не трогаем или сбрасываем
        # check_facts все равно его сбросит, так что можно вернуть {}
        pass
        # Или явно сбросить: update["fact_added_in_last_run"] = False

    return update
