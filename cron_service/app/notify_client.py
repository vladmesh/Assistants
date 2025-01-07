import os
import requests

TG_BOT_URL = os.getenv("TG_BOT_URL", "http://bot:8000")

def send_notification(chat_id: int, message: str) -> None:
    """Отправляет уведомление через tg_bot API."""
    url = f"{TG_BOT_URL}/api/notify/"
    print(chat_id, message)
    response = requests.post(url, json={"chat_id": chat_id, "message": message})
    if response.status_code == 200:
        print("Уведомление успешно отправлено.")
    else:
        print(f"Ошибка при отправке уведомления: {response.status_code} - {response.text}")
