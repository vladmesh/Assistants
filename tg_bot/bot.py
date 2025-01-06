import os
import threading

import uvicorn

from fastapi import FastAPI
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

from api.notify import router as notify_router
from commands.start import start
from commands.tasks import tasks, edit_task, edit_status, set_status, edit_description, set_description
from commands.new_task import add_task, handle_new_task, skip_description
from commands.show_menu import show_menu


app = FastAPI()
app.include_router(notify_router, prefix="/api")

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


def start_telegram_bot():
    application.run_polling()


def start_fastapi() -> None:
    """
    Запускаем uvicorn в асинхронном режиме.
    """
    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        # При желании можно прописать reload=True, но это уже на ваше усмотрение.
    )


def main():
    bot_thread = threading.Thread(target=start_fastapi, daemon=True)
    bot_thread.start()

    # 2. В главном потоке запускаем FastAPI
    start_telegram_bot()


if __name__ == "__main__":
    main()
