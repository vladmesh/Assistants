"""User fixtures"""
from models import TelegramUser

def create_test_users() -> list[TelegramUser]:
    """Create test users fixtures"""
    return [
        TelegramUser(telegram_id=625038902, username="vladmesh"),
        TelegramUser(telegram_id=7192299, username="vladislav_mesh88k")
    ] 