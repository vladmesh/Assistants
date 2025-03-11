from apscheduler.schedulers.background import BackgroundScheduler
from redis_client import send_notification
from rest_client import fetch_scheduled_jobs
import os
import time
import logging
from pytz import utc

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID = int(os.getenv("TELEGRAM_ID", "0"))
MAX_RETRIES = 3
RETRY_DELAY = 5  # секунды

# Создаем планировщик с явным указанием UTC
scheduler = BackgroundScheduler(timezone=utc)


def start_scheduler():
    """Запускает планировщик задач."""
    try:
        # Периодически обновляет задачи из REST-сервиса
        scheduler.add_job(update_jobs_from_rest, "interval", minutes=1)
        scheduler.start()
        logger.info("Планировщик успешно запущен")
        
        # Держим процесс активным
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.shutdown()
            logger.info("Планировщик остановлен")
            
    except Exception as e:
        logger.error(f"Ошибка при запуске планировщика: {e}")
        scheduler.shutdown()
        raise


def update_jobs_from_rest():
    """Обновляет задачи в планировщике, запрашивая их у REST-сервиса."""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            logger.info("Обновляем список задач из REST-сервиса...")
            logger.info(f"REST_SERVICE_URL: {os.getenv('REST_SERVICE_URL', 'http://rest_service:8000')}")
            jobs = fetch_scheduled_jobs()
            logger.info(f"Полученные задачи: {jobs}")
            
            # Удаляем задачи, которых больше нет в REST-сервисе
            current_jobs = {f"job_{job['id']}" for job in jobs}
            logger.info(f"Текущие ID задач: {current_jobs}")
            
            for job in scheduler.get_jobs():
                logger.info(f"Проверяем задачу: {job.id} ({job.name})")
                if job.id not in current_jobs:
                    scheduler.remove_job(job.id)
                    logger.info(f"Задача {job.name} удалена")
            
            # Добавляем или обновляем задачи
            for job in jobs:
                job_id = f"job_{job['id']}"
                logger.info(f"Обрабатываем задачу: {job_id} ({job['name']})")
                if not scheduler.get_job(job_id):
                    try:
                        cron_args = parse_cron_expression(job["cron_expression"])
                        logger.info(f"CRON аргументы: {cron_args}")
                        scheduler.add_job(
                            execute_job,
                            trigger="cron",
                            id=job_id,
                            name=job["name"],
                            args=[job],
                            **cron_args,
                        )
                        logger.info(f"Задача {job['name']} добавлена")
                    except Exception as e:
                        logger.error(f"Ошибка при добавлении задачи {job['name']}: {e}")
                else:
                    logger.info(f"Задача {job['name']} уже существует")
            
            logger.info("Список задач успешно обновлен")
            return
            
        except Exception as e:
            retries += 1
            logger.error(f"Ошибка при обновлении задач (попытка {retries}/{MAX_RETRIES}): {e}")
            if retries < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Превышено максимальное количество попыток обновления задач")
                raise  # Пробрасываем исключение дальше


def parse_cron_expression(cron_expression: str) -> dict:
    """
    Парсит строку CRON-выражения и преобразует её в аргументы для APScheduler.
    Все времена интерпретируются как UTC.
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
        "timezone": utc  # Явно указываем UTC для каждой задачи
    }


def execute_job(job):
    """Выполняет задачу."""
    try:
        logger.info(f"Выполняем задачу: {job['name']}")
        send_notification(CHAT_ID, f"Запланированная задача: {job['name']}")
        logger.info(f"Задача {job['name']} успешно выполнена")
    except Exception as e:
        logger.error(f"Ошибка при выполнении задачи {job['name']}: {e}")
