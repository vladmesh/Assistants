import os

from pydantic import BaseModel
from fastapi import APIRouter
from telegram import Bot

class Notification(BaseModel):
    chat_id: int
    message: str

router = APIRouter()

@router.post("/notify/")
async def send_notification(notification: Notification):
    token = os.getenv("TELEGRAM_TOKEN")
    bot = Bot(token=token)

    await bot.send_message(chat_id=notification.chat_id, text=notification.message)
    return {"status": "success"}
