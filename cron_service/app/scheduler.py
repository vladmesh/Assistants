from apscheduler.schedulers.blocking import BlockingScheduler
from notify_client import send_notification
import os

CHAT_ID = int(os.getenv("TELEGRAM_ID", "0"))

def start_scheduler():
    scheduler = BlockingScheduler()

    # Задача, выполняющаяся раз в минуту
    scheduler.add_job(send_minute_checkin, "interval", minutes=1)

    scheduler.start()

def send_minute_checkin():
    """Функция отправляет сообщение в Telegram раз в минуту."""
    send_notification(CHAT_ID, "Привет! Напоминаю, что прошло ещё одна минута.")
