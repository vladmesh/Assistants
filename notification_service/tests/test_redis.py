import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, Mock
from app.main import app
from telegram.error import TelegramError
import json

client = TestClient(app)

@pytest.fixture
def mock_telegram_bot():
    with patch("app.main.bot") as mock_bot:
        mock_bot.send_message = AsyncMock()
        yield mock_bot

@pytest.fixture
def mock_redis():
    with patch("app.main.redis_client") as mock_redis:
        mock_redis.ping = Mock(return_value=True)
        mock_redis.setex = Mock()
        mock_redis.keys = Mock(return_value=["notification:123:test"])
        mock_redis.get = Mock(return_value=json.dumps({
            "chat_id": 123,
            "message": "test",
            "priority": "normal"
        }))
        mock_redis.delete = Mock(return_value=True)
        yield mock_redis

def test_redis_storage_on_error(mock_telegram_bot, mock_redis):
    """Тест сохранения уведомления в Redis при ошибке отправки."""
    mock_telegram_bot.send_message.side_effect = TelegramError("Telegram API Error")
    
    notification_data = {
        "chat_id": 123,
        "message": "test",
        "priority": "normal"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 500
    
    # Проверяем, что данные были сохранены в Redis
    mock_redis.setex.assert_called_once()
    args = mock_redis.setex.call_args[0]
    assert args[0].startswith("notification:123:test")
    assert args[1] == 3600  # TTL
    assert json.loads(args[2]) == notification_data

def test_redis_retry_mechanism(mock_telegram_bot, mock_redis):
    """Тест механизма повторной отправки уведомлений из Redis."""
    # Имитируем успешную отправку после ошибки
    mock_telegram_bot.send_message.side_effect = [
        TelegramError("Telegram API Error"),
        AsyncMock()
    ]
    
    # Первая попытка отправки (должна сохраниться в Redis)
    notification_data = {
        "chat_id": 123,
        "message": "test",
        "priority": "normal"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 500
    
    # Проверяем, что данные были сохранены в Redis
    mock_redis.setex.assert_called_once()
    
    # Вторая попытка отправки (должна быть успешной)
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_redis_connection_error(mock_telegram_bot, mock_redis):
    """Тест обработки ошибки подключения к Redis."""
    mock_redis.ping.side_effect = Exception("Redis Connection Error")
    
    response = client.get("/api/health/")
    assert response.status_code == 503
    assert "Сервис нездоров" in response.json()["detail"] 