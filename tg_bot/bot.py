from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from rest_service.rest_service import RestService
from rest_service.models import Task, TaskStatus
import os

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f'Hello {update.effective_user.first_name}')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветственное сообщение и создание пользователя."""
    telegram_id = update.message.from_user.id
    username = update.message.from_user.username
    rest_service = RestService()
    # Получить или создать пользователя
    user = rest_service.get_or_create_user(telegram_id=telegram_id, username=username)

    await update.message.reply_text(
        f"Привет, {user.username or 'пользователь'}! Я помогу управлять твоими задачами. Вот что я умею:\n"
        "/tasks - посмотреть задачи\n"
    )

async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вывод списка задач с кнопками."""
    telegram_id = str(update.message.from_user.id)
    rest_service = RestService()
    tasks_list = rest_service.get_tasks(user_id=int(telegram_id))

    if not tasks_list:
        await update.message.reply_text("У тебя пока нет задач.")
        return

    # Создание кнопок для каждой задачи
    buttons = [
        [InlineKeyboardButton(task.text, callback_data=f"task_{task.id}")]
        for task in tasks_list
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await update.message.reply_text("Вот список твоих задач:", reply_markup=keyboard)

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
        f"Что ты хочешь сделать с задачей '{task.text}'?", reply_markup=keyboard
    )

async def edit_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка изменения статуса задачи."""
    query = update.callback_query
    await query.answer()

    # Извлечение ID задачи из callback_data
    task_id = int(query.data.split("_")[1])
    rest_service = RestService()

    # Получение текущей задачи
    task = rest_service.get_task(task_id=task_id)

    # Кнопки с выбором статуса
    buttons = [
        [InlineKeyboardButton(status.value, callback_data=f"setstatus_{task_id}_{status.name}")]
        for status in TaskStatus
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(
        f"Выбери новый статус для задачи '{task.text}':", reply_markup=keyboard
    )


async def set_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Установка нового статуса задачи."""
    query = update.callback_query
    await query.answer()

    # Извлечение данных из callback_data
    data = query.data.split("_")
    task_id = int(data[1])
    new_status = data[2]

    rest_service = RestService()

    # Получение текущей задачи
    task = rest_service.get_task(task_id=task_id)

    # Обновление статуса в модели задачи
    task.status = TaskStatus[new_status]

    print(task.status)

    # Вызов update_task с обновлённой моделью
    updated_task = rest_service.update_task(task_id=task_id, task=task)

    await query.edit_message_text(f"Статус задачи обновлён на {updated_task.status.value}.")


token = os.getenv('TELEGRAM_TOKEN')
app = ApplicationBuilder().token(token).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("tasks", tasks))

app.add_handler(CallbackQueryHandler(edit_task, pattern=r"^task_\d+$"))
app.add_handler(CallbackQueryHandler(edit_status, pattern=r"^status_\d+$"))
app.add_handler(CallbackQueryHandler(set_status, pattern=r"^setstatus_\d+_[A-Z]+$"))


app.run_polling()