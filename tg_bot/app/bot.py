from telegram.ext import (
    ApplicationBuilder,
    CommandHandler as TelegramCommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from app.config import load_config
from app.handlers.commands import CommandHandler
from app.handlers.task_handler import TaskHandler
from app.rest_client import RestClient
import logging

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def setup_handlers(application):
    """Настраивает обработчики команд и callback-запросов."""
    # Инициализируем REST клиент и обработчики
    rest_client = RestClient()
    command_handler = CommandHandler(rest_client)
    task_handler = TaskHandler(rest_client)
    
    # Команды
    application.add_handler(TelegramCommandHandler("start", command_handler.start))
    application.add_handler(TelegramCommandHandler("skip", task_handler.skip_description))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Показать меню"), command_handler.show_menu))
    
    # Callback-запросы
    application.add_handler(CallbackQueryHandler(task_handler.add_task, pattern=r"^add_task$"))
    application.add_handler(CallbackQueryHandler(task_handler.list_tasks, pattern=r"^view_tasks$"))
    application.add_handler(CallbackQueryHandler(task_handler.update_task_status, pattern=r"^setstatus_\d+_[A-Z]+$"))
    
    # Обработка текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, task_handler.handle_new_task))


def main():
    """Запускает бота."""
    try:
        config = load_config()
        application = ApplicationBuilder().token(config.token).build()
        
        setup_handlers(application)
        logger.info("Starting bot...")
        application.run_polling()
    except Exception as e:
        logger.error("Failed to start bot", exc_info=True)
        raise


if __name__ == "__main__":
    main() 