from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from app.config import load_config
from app.handlers import commands, callbacks


def setup_handlers(application):
    """Настраивает обработчики команд и callback-запросов."""
    # Команды
    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("skip", callbacks.skip_description))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Показать меню"), commands.show_menu))
    
    # Callback-запросы
    application.add_handler(CallbackQueryHandler(callbacks.add_task, pattern=r"^add_task$"))
    application.add_handler(CallbackQueryHandler(callbacks.tasks, pattern=r"^view_tasks$"))
    application.add_handler(CallbackQueryHandler(callbacks.edit_task, pattern=r"^task_\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.edit_status, pattern=r"^status_\d+$"))
    application.add_handler(CallbackQueryHandler(callbacks.set_status, pattern=r"^setstatus_\d+_[A-Z]+$"))
    
    # Обработка текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callbacks.handle_new_task))


def main():
    """Запускает бота."""
    config = load_config()
    application = ApplicationBuilder().token(config.token).build()
    
    setup_handlers(application)
    application.run_polling()


if __name__ == "__main__":
    main() 