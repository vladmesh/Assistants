from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру главного меню."""
    keyboard = [
        [
            InlineKeyboardButton("📝 Добавить задачу", callback_data="add_task"),
            InlineKeyboardButton("📋 Список задач", callback_data="view_tasks")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для управления задачей."""
    keyboard = [
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"task_{task_id}"),
            InlineKeyboardButton("📝 Описание", callback_data=f"description_{task_id}")
        ],
        [
            InlineKeyboardButton("✅ Статус", callback_data=f"status_{task_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_status_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора статуса задачи."""
    keyboard = [
        [
            InlineKeyboardButton("⏳ В процессе", callback_data=f"setstatus_{task_id}_IN_PROGRESS"),
            InlineKeyboardButton("✅ Завершено", callback_data=f"setstatus_{task_id}_COMPLETED")
        ],
        [
            InlineKeyboardButton("❌ Отменено", callback_data=f"setstatus_{task_id}_CANCELLED")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def format_task_message(task: dict) -> str:
    """Форматирует сообщение с информацией о задаче."""
    return (
        f"📋 *{task['title']}*\n"
        f"Статус: {task['status']}\n"
        f"Описание: {task.get('description', 'Нет описания')}"
    ) 