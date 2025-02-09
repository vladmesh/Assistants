from telegram import Update
from telegram.ext import ContextTypes

from rest_service.models import Task, TaskStatus
from rest_service.rest_service import RestService

from commands.show_menu import show_menu


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начало создания новой задачи через инлайн-кнопку."""
    query = update.callback_query
    await query.answer()  # Подтверждаем запрос, чтобы убрать "загрузку" на кнопке

    context.user_data["new_task_stage"] = "waiting_for_title"
    await query.edit_message_text("Напиши название новой задачи.")

async def handle_new_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ввода данных для новой задачи."""
    telegram_id = str(update.message.from_user.id)

    if not "new_task_stage" in context.user_data:
        await update.message.reply_text("Для создания задачи используй команду /new_task.")
        return

    rest_service = RestService()

    if context.user_data["new_task_stage"] == "waiting_for_title":
        # Сохранить название задачи и перейти к следующему этапу
        context.user_data["title"] = update.message.text
        context.user_data["new_task_stage"] = "waiting_for_description"
        await update.message.reply_text("Теперь напиши описание задачи (или напиши /skip, чтобы пропустить).")

    elif context.user_data["new_task_stage"] == "waiting_for_description":
        # Сохранить описание задачи и создать задачу
        description = update.message.text
        title = context.user_data["title"]
        telegram_user = rest_service.get_or_create_user(
            telegram_id=int(telegram_id), username=update.message.from_user.username
        )

        task = Task(title=title, user_id=telegram_user.id, status=TaskStatus.ACTIVE)
        task.description = description  # Добавляем описание, если оно есть

        # Отправить задачу в REST API

        task.user_id = telegram_user.id
        created_task = rest_service.create_task(task)

        await update.message.reply_text(f"Задача создана: {created_task.title}")
        context.user_data.clear()
        await show_menu(update, context)

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка пропуска описания."""
    telegram_id = str(update.message.from_user.id)

    if not "new_task_stage" in context.user_data or context.user_data["new_task_stage"] != "waiting_for_description":
        await update.message.reply_text("Для создания задачи используй команду /new_task.")
        return

    title = context.user_data["title"]

    rest_service = RestService()

    # Отправить задачу в REST API
    telegram_user = rest_service.get_or_create_user(
        telegram_id=int(telegram_id), username=update.message.from_user.username
    )
    task = Task(title=title, user_id=telegram_user.id, status=TaskStatus.ACTIVE)
    created_task = rest_service.create_task(task)

    await update.message.reply_text(f"Задача создана: {created_task.title}")
    context.user_data.clear()
    await show_menu(update, context)