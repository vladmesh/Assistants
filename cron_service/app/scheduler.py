from apscheduler.schedulers.blocking import BlockingScheduler
from notify_client import send_notification
from rest_client import fetch_scheduled_jobs
import os

CHAT_ID = int(os.getenv("TELEGRAM_ID", "0"))

scheduler = BlockingScheduler()


def start_scheduler():
    """Запускает планировщик задач."""
    # Периодически обновляет задачи из REST-сервиса
    scheduler.add_job(update_jobs_from_rest, "interval", minutes=1)

    scheduler.start()


def update_jobs_from_rest():
    """Обновляет задачи в планировщике, запрашивая их у REST-сервиса."""
    print("Обновляем список задач из REST-сервиса...")
    jobs = fetch_scheduled_jobs()
    for job in jobs:
        job_id = f"job_{job['id']}"
        if not scheduler.get_job(job_id):
            scheduler.add_job(
                execute_job,
                trigger="cron",
                id=job_id,
                name=job["name"],
                args=[job],
                **parse_cron_expression(job["cron_expression"]),
            )
            print(f"Задача {job['name']} добавлена.")
        else:
            print(f"Задача {job['name']} уже существует.")
    scheduler.print_jobs()


def parse_cron_expression(cron_expression: str) -> dict:
    """
    Парсит строку CRON-выражения и преобразует её в аргументы для APScheduler.
    """
    parts = cron_expression.split()
    if len(parts) != 5:
        raise ValueError(f"Неверный формат CRON-выражения: {cron_expression}")

    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def execute_job(job):
    """Выполняет задачу."""
    print(f"Выполняем задачу: {job['name']}")
    send_notification(CHAT_ID, f"Запланированная задача: {job['name']}")
