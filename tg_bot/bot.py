import os
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from commands.start import start
from commands.tasks import tasks, edit_task, edit_status, set_status, edit_description, set_description
from commands.new_task import add_task, handle_new_task, skip_description
from commands.show_menu import show_menu

# --- Инициализация бота ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
application = ApplicationBuilder().token(TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & filters.Regex("Показать меню"), show_menu))

application.add_handler(CallbackQueryHandler(edit_task, pattern=r"^task_\d+$"))
application.add_handler(CallbackQueryHandler(edit_status, pattern=r"^status_\d+$"))
application.add_handler(CallbackQueryHandler(set_status, pattern=r"^setstatus_\d+_[A-Z]+$"))
application.add_handler(CallbackQueryHandler(edit_status, pattern=r"description_\d+$"))
application.add_handler(CallbackQueryHandler(set_status, pattern=r"^setstatus_\d+_[A-Z]+$"))

application.add_handler(CallbackQueryHandler(add_task, pattern=r"^add_task$"))
application.add_handler(CallbackQueryHandler(tasks, pattern=r"^view_tasks"))
application.add_handler(CommandHandler("skip", skip_description))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_task))


def main():
    application.run_polling()


if __name__ == "__main__":
    main()
