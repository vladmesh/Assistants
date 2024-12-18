from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from rest_service.rest_service import RestService
from rest_service.models import Task, TaskStatus
import os

USER_STATE = {}

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
        [InlineKeyboardButton(task.title, callback_data=f"task_{task.id}")]
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
        f"Что ты хочешь сделать с задачей '{task.title}'?", reply_markup=keyboard
    )

async def edit_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка изменения описания задачи"""
    query = update.callback_query
    await query.answer()

    task_id = int(query.data.split("_")[1])
    rest_service = RestService()

    task = rest_service.get_task(task_id=task_id)
    await query.edit_message_text(
        f"Выбери новый статус для задачи '{task.title}':", reply_markup=keyboard
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
        for status in TaskStatus if status.value != task.status.value
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(
        f"Выбери новый статус для задачи '{task.title}':", reply_markup=keyboard
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

async def new_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начало создания новой задачи."""
    telegram_id = str(update.message.from_user.id)
    USER_STATE[telegram_id] = {"stage": "waiting_for_title"}
    await update.message.reply_text("Напиши название новой задачи.")

async def handle_new_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка ввода данных для новой задачи."""
    telegram_id = str(update.message.from_user.id)
    user_state = USER_STATE.get(telegram_id)

    if not user_state:
        await update.message.reply_text("Для создания задачи используй команду /new_task.")
        return

    rest_service = RestService()

    if user_state["stage"] == "waiting_for_title":
        # Сохранить название задачи и перейти к следующему этапу
        user_state["title"] = update.message.text
        user_state["stage"] = "waiting_for_description"
        await update.message.reply_text("Теперь напиши описание задачи (или напиши /skip, чтобы пропустить).")

    elif user_state["stage"] == "waiting_for_description":
        # Сохранить описание задачи и создать задачу
        description = update.message.text
        title = user_state["title"]
        telegram_user = rest_service.get_or_create_user(
            telegram_id=int(telegram_id), username=update.message.from_user.username
        )

        task = Task(title=title, user_id=telegram_user.id, status=TaskStatus.ACTIVE)
        task.description = description  # Добавляем описание, если оно есть

        # Отправить задачу в REST API

        task.user_id = telegram_user.id
        created_task = rest_service.create_task(task)

        await update.message.reply_text(f"Задача создана: {created_task.title}")
        USER_STATE.pop(telegram_id, None)  # Удалить состояние пользователя

async def skip_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка пропуска описания."""
    telegram_id = str(update.message.from_user.id)
    user_state = USER_STATE.get(telegram_id)

    if not user_state or user_state["stage"] != "waiting_for_description":
        await update.message.reply_text("Для создания задачи используй команду /new_task.")
        return

    title = user_state["title"]

    rest_service = RestService()

    # Отправить задачу в REST API
    telegram_user = rest_service.get_or_create_user(
        telegram_id=int(telegram_id), username=update.message.from_user.username
    )
    task = Task(title=title, user_id=telegram_user.id, status=TaskStatus.ACTIVE)
    created_task = rest_service.create_task(task)

    await update.message.reply_text(f"Задача создана: {created_task.title}")
    USER_STATE.pop(telegram_id, None)  # Удалить состояние пользователя


token = os.getenv('TELEGRAM_TOKEN')
app = ApplicationBuilder().token(token).build()

app.add_handler(CommandHandler("hello", hello))
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("tasks", tasks))

app.add_handler(CallbackQueryHandler(edit_task, pattern=r"^task_\d+$"))
app.add_handler(CallbackQueryHandler(edit_status, pattern=r"^status_\d+$"))
app.add_handler(CallbackQueryHandler(set_status, pattern=r"^setstatus_\d+_[A-Z]+$"))
app.add_handler(CommandHandler("new_task", new_task))
app.add_handler(CommandHandler("skip", skip_description))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_task))



app.run_polling()