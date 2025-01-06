from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from rest_service.models import TaskStatus
from rest_service.rest_service import RestService

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from commands.show_menu import show_menu


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вывод списка задач с кнопками."""
    query = update.callback_query
    await query.answer()  # Подтверждаем callback, чтобы убрать "загрузку" на кнопке

    telegram_id = str(update.effective_user.id)
    rest_service = RestService()
    tasks_list = rest_service.get_active_tasks(user_id=int(telegram_id))

    if not tasks_list:
        await query.edit_message_text("У тебя пока нет задач.")
        return

    # Создание кнопок для каждой задачи
    buttons = [
        [InlineKeyboardButton(task.title, callback_data=f"task_{task.id}")]
        for task in tasks_list
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await query.edit_message_text("Вот список твоих задач:", reply_markup=keyboard)



async def edit_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка кнопки редактирования задачи."""
    query = update.callback_query
    await query.answer()  # Закрываем всплывающее окно Telegram

    task_id = int(query.data.split("_")[1])  # Извлечение ID задачи из callback_data
    rest_service = RestService()
    task = rest_service.get_task(task_id=task_id)

    # Меню редактирования задачи
    buttons = [
        [InlineKeyboardButton("Изменить статус", callback_data=f"status_{task.id}")],
        [InlineKeyboardButton("Изменить описание", callback_data=f"description_{task.id}")],
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(
        f"Что ты хочешь сделать с задачей '{task.title}'?", reply_markup=keyboard
    )


async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка изменения описания задачи."""
    query = update.callback_query
    await query.answer()  # Закрываем всплывающее окно Telegram

    task_id = int(query.data.split("_")[1])
    rest_service = RestService()
    task = rest_service.get_task(task_id=task_id)

    await query.edit_message_text(f"Текущее описание задачи '{task.title}': {task.description}\n\n"
                                  f"Отправь отдельное сообщение с новым описанием для задачи.")

    context.user_data["task_id"] = task_id
    context.user_data["awaiting_description"] = True


async def set_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка нового описания задачи."""
    if not context.user_data.get("awaiting_description"):
        await update.message.reply_text("Нет активного запроса на изменение описания.")
        return

    new_description = update.message.text
    task_id = context.user_data["task_id"]
    rest_service = RestService()

    task = rest_service.get_task(task_id=task_id)
    task.description = new_description
    updated_task = rest_service.update_task(task_id=task_id, task=task)

    context.user_data.pop("task_id", None)
    context.user_data.pop("awaiting_description", None)

    await update.message.reply_text(f"Описание задачи '{updated_task.title}' успешно обновлено.")
    await show_menu(update, context)




async def edit_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка изменения статуса задачи."""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split("_")[1])
    rest_service = RestService()
    task = rest_service.get_task(task_id=task_id)

    buttons = [
        [InlineKeyboardButton(status.value, callback_data=f"setstatus_{task_id}_{status.name}")]
        for status in TaskStatus if status != task.status
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(
        f"Выбери новый статус для задачи '{task.title}':", reply_markup=keyboard
    )

async def set_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка нового статуса задачи."""
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    task_id = int(data[1])
    new_status = data[2]

    rest_service = RestService()
    task = rest_service.get_task(task_id=task_id)
    task.status = TaskStatus[new_status]

    updated_task = rest_service.update_task(task_id=task_id, task=task)

    await query.edit_message_text(f"Статус задачи обновлён на {updated_task.status.value}.")
    await show_menu(update, context)


