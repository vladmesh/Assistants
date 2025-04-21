"""Tool fixtures for database initialization"""

from typing import List, Union
from uuid import uuid4

# from models import Tool, ToolType
from models.assistant import Tool, ToolType  # Models are in models/assistant.py


def create_time_tool() -> Tool:
    """Create TimeTool fixture"""
    return Tool(
        name="time",
        tool_type=ToolType.TIME.value,
        description="Получить текущее время в указанном часовом поясе",
        is_active=True,
    )


def create_calendar_create_tool() -> Tool:
    """Create CalendarCreateTool fixture"""
    return Tool(
        name="calendar_create",
        tool_type=ToolType.CALENDAR.value,
        description=(
            "Создает новое событие в Google Calendar. Параметры: "
            "title (обязательно), start_time (обязательно), "
            "end_time (обязательно), description (опционально), "
            "location (опционально)"
        ),
        is_active=True,
    )


def create_calendar_list_tool() -> Tool:
    """Create CalendarListTool fixture"""
    return Tool(
        name="calendar_list",
        tool_type=ToolType.CALENDAR.value,
        description=(
            "Получает список событий из Google Calendar. Параметры: "
            "time_min (опционально), time_max (опционально). "
            "Если время не указано, возвращает события на ближайшую неделю."
        ),
        is_active=True,
    )


def create_reminder_tool() -> Tool:
    """Create ReminderTool fixture"""
    return Tool(
        name="reminder",
        tool_type=ToolType.REMINDER.value,
        description=(
            "Инструмент для создания напоминаний. Есть два способа указать "
            "время напоминания: 1. delay_seconds - через сколько секунд "
            "отправить напоминание 2. datetime_str + timezone - конкретные "
            "дата/время и часовой пояс"
        ),
        is_active=True,
    )


def create_sub_assistant_tool(writer_id: str) -> Tool:
    """Create SubAssistantTool fixture"""
    return Tool(
        name="sub_assistant",
        tool_type=ToolType.SUB_ASSISTANT.value,
        description=(
            "Инструмент для делегирования задач специализированному ассистенту. "
            "Используется для анализа сложных текстов, генерации "
            "специализированного контента, решения узкоспециализированных задач."
        ),
        is_active=True,
    )


def get_all_tools(writer_id: str) -> list[Tool]:
    """Get all tool fixtures"""
    return [
        create_time_tool(),
        create_calendar_create_tool(),
        create_calendar_list_tool(),
        create_reminder_tool(),
        create_sub_assistant_tool(writer_id),
    ]
