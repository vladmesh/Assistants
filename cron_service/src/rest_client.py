import os
import requests
import logging

logger = logging.getLogger(__name__)

REST_SERVICE_URL = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")


def fetch_scheduled_jobs():
    """Получает список запланированных задач от REST-сервиса."""
    url = f"{REST_SERVICE_URL}/api/cronjobs/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        jobs = response.json()
        logger.info(f"Получено задач: {len(jobs)}")
        return jobs
    except requests.RequestException as e:
        logger.error(f"Ошибка при получении задач: {e}")
        return []
