import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification_service:8000")

def send_notification(chat_id: int, message: str, priority: str = "normal") -> None:
    """
    Отправляет уведомление через notification_service.
    
    Args:
        chat_id: ID чата в Telegram
        message: Текст сообщения
        priority: Приоритет уведомления (normal, high, low)
    """
    url = f"{NOTIFICATION_SERVICE_URL}/api/notify/"
    data = {
        "chat_id": chat_id,
        "message": message,
        "priority": priority
    }
    
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            logger.info("Уведомление успешно отправлено.")
        else:
            logger.error(f"Ошибка при отправке уведомления: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при отправке уведомления: {str(e)}")
