import os
from enum import Enum
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telegram import Bot
from telegram.error import TelegramError
import redis
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

app = FastAPI(title="Notification Service")

# Инициализация Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0
)

# Инициализация Telegram бота
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не установлен")
bot = Bot(token=TELEGRAM_TOKEN)

class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"

class Notification(BaseModel):
    chat_id: int
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL

@app.post("/api/notify/")
async def send_notification(notification: Notification):
    """
    Отправляет уведомление через Telegram.
    Если отправка не удалась, сохраняет в Redis для повторной попытки.
    """
    try:
        await bot.send_message(
            chat_id=notification.chat_id,
            text=notification.message
        )
        return {"status": "success", "message": "Уведомление отправлено"}
    except TelegramError as e:
        # Сохраняем уведомление в Redis для повторной попытки
        notification_key = f"notification:{notification.chat_id}:{notification.message}"
        redis_client.setex(
            notification_key,
            3600,  # Храним 1 час
            notification.model_dump_json()
        )
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при отправке уведомления: {str(e)}"
        )

@app.get("/api/health/")
async def health_check():
    """Проверка работоспособности сервиса."""
    try:
        # Проверяем подключение к Redis
        redis_client.ping()
        # Проверяем подключение к Telegram API
        await bot.get_me()
        return {"status": "healthy"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Сервис нездоров: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000))
    ) 