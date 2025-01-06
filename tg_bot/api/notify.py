import os

from fastapi import APIRouter
from telegram import Bot

router = APIRouter()

@router.post("/notify/")
async def send_notification(chat_id: int, message: str):
    token = os.getenv('TELEGRAM_TOKEN')
    bot = Bot(token=token)
    await bot.send_message(chat_id=chat_id, text=message)
    return {"status": "success"}
