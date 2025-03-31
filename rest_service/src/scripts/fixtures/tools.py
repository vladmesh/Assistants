"""Tool fixtures for database initialization"""

from models import Tool, ToolType
from uuid import UUID


def create_time_tool() -> Tool:
    """Create TimeTool fixture"""
    return Tool(
        name="time",
        tool_type=ToolType.TIME.value,
        description="Получить текущее время в указанном часовом поясе",
        input_schema='{"type": "object", "properties": {"timezone": {"type": "string", "description": "Часовой пояс (например, Europe/Moscow)"}}, "required": ["timezone"]}',
        is_active=True,
    )


def create_calendar_create_tool() -> Tool:
    """Create CalendarCreateTool fixture"""
    return Tool(
        name="calendar_create",
        tool_type=ToolType.CALENDAR.value,
        description="Создает новое событие в Google Calendar. Параметры: title (обязательно), start_time (обязательно), end_time (обязательно), description (опционально), location (опционально)",
        input_schema='{"type": "object", "properties": {"title": {"type": "string"}, "start_time": {"type": "object", "properties": {"date_time": {"type": "string", "format": "date-time"}, "time_zone": {"type": "string", "default": "UTC"}}, "required": ["date_time"]}, "end_time": {"type": "object", "properties": {"date_time": {"type": "string", "format": "date-time"}, "time_zone": {"type": "string", "default": "UTC"}}, "required": ["date_time"]}, "description": {"type": "string"}, "location": {"type": "string"}}, "required": ["title", "start_time", "end_time"]}',
        is_active=True,
    )


def create_calendar_list_tool() -> Tool:
    """Create CalendarListTool fixture"""
    return Tool(
        name="calendar_list",
        tool_type=ToolType.CALENDAR.value,
        description="Получает список событий из Google Calendar. Параметры: time_min (опционально), time_max (опционально). Если время не указано, возвращает события на ближайшую неделю.",
        input_schema='{"type": "object", "properties": {"time_min": {"type": "string", "format": "date-time"}, "time_max": {"type": "string", "format": "date-time"}}}',
        is_active=True,
    )


def create_reminder_tool() -> Tool:
    """Create ReminderTool fixture"""
    return Tool(
        name="reminder",
        tool_type=ToolType.REMINDER.value,
        description="Инструмент для создания напоминаний. Есть два способа указать время напоминания: 1. delay_seconds - через сколько секунд отправить напоминание 2. datetime_str + timezone - конкретные дата/время и часовой пояс",
        input_schema='{"type": "object", "properties": {"message": {"type": "string"}, "delay_seconds": {"type": "integer", "minimum": 1}, "datetime_str": {"type": "string", "format": "date-time"}, "timezone": {"type": "string"}}, "required": ["message"], "oneOf": [{"required": ["delay_seconds"]}, {"required": ["datetime_str", "timezone"]}]}',
        is_active=True,
    )


def create_sub_assistant_tool(writer_id: str) -> Tool:
    """Create SubAssistantTool fixture"""
    return Tool(
        name="sub_assistant",
        tool_type=ToolType.SUB_ASSISTANT.value,
        description="Инструмент для делегирования задач специализированному ассистенту. Используется для анализа сложных текстов, генерации специализированного контента, решения узкоспециализированных задач.",
        input_schema='{"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}',
        assistant_id=UUID(writer_id),  # Convert string ID to UUID
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
