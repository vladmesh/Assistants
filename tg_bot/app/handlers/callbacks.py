from telegram import Update
from telegram.ext import ContextTypes

from app.utils.keyboard import get_task_keyboard, get_status_keyboard, format_task_message, get_main_menu_keyboard
from app.rest_client import RestClient


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик добавления новой задачи."""
    query = update.callback_query
    await query.answer()
    
    context.user_data["state"] = "waiting_for_task_name"
    await query.message.reply_text("Введите название задачи:")


async def handle_new_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ввода новой задачи."""
    if context.user_data.get("state") == "waiting_for_task_name":
        context.user_data["task_name"] = update.message.text
        context.user_data["state"] = "waiting_for_task_description"
        await update.message.reply_text("Введите описание задачи (или отправьте /skip):")
    elif context.user_data.get("state") == "waiting_for_task_description":
        context.user_data["task_description"] = update.message.text
        
        # Получаем или создаем пользователя
        rest_client = RestClient()
        user = rest_client.get_or_create_user(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username
        )
        
        # Создаем задачу
        task = rest_client.create_task(
            user_id=user["id"],
            name=context.user_data["task_name"],
            description=context.user_data["task_description"]
        )
        
        await update.message.reply_text(
            "✅ Задача создана!",
            reply_markup=get_main_menu_keyboard()
        )
        context.user_data.clear()


async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик пропуска описания задачи."""
    if context.user_data.get("state") == "waiting_for_task_description":
        context.user_data["task_description"] = "Нет описания"
        
        # Получаем или создаем пользователя
        rest_client = RestClient()
        user = rest_client.get_or_create_user(
            telegram_id=update.effective_user.id,
            username=update.effective_user.username
        )
        
        # Создаем задачу
        task = rest_client.create_task(
            user_id=user["id"],
            name=context.user_data["task_name"],
            description=context.user_data["task_description"]
        )
        
        await update.message.reply_text(
            "✅ Задача создана!",
            reply_markup=get_main_menu_keyboard()
        )
        context.user_data.clear()


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список задач."""
    query = update.callback_query
    await query.answer()
    
    # Получаем задачи пользователя
    rest_client = RestClient()
    user = rest_client.get_or_create_user(
        telegram_id=update.effective_user.id,
        username=update.effective_user.username
    )
    tasks_list = rest_client.get_user_tasks(user["id"])
    
    if not tasks_list:
        await query.message.reply_text(
            "У вас пока нет задач.",
            reply_markup=get_main_menu_keyboard()
        )
        return
    
    message = "📋 Ваши задачи:\n\n"
    for task in tasks_list:
        message += format_task_message(task) + "\n\n"
    
    await query.message.reply_text(
        message,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


async def edit_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик редактирования задачи."""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[1])
    # TODO: Получение задачи из базы данных
    task = {"id": task_id, "name": "Тестовая задача", "status": "В процессе"}
    
    await query.message.reply_text(
        format_task_message(task),
        reply_markup=get_task_keyboard(task_id),
        parse_mode="Markdown"
    )


async def edit_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик изменения статуса задачи."""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.split("_")[1])
    await query.message.reply_text(
        "Выберите новый статус:",
        reply_markup=get_status_keyboard(task_id)
    )


async def set_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик установки статуса задачи."""
    query = update.callback_query
    await query.answer()
    
    _, task_id, status = query.data.split("_")
    
    # Обновляем статус задачи
    rest_client = RestClient()
    task = rest_client.update_task_status(task_id, status)
    
    await query.message.reply_text(
        f"✅ Статус задачи обновлен на: {status}",
        reply_markup=get_main_menu_keyboard()
    ) 