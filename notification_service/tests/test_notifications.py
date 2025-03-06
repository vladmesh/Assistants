import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, Mock
from app.main import app
from telegram.error import TelegramError

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
        yield mock_redis

def test_send_notification_success(mock_telegram_bot):
    """Тест успешной отправки уведомления."""
    notification_data = {
        "chat_id": 123456789,
        "message": "Тестовое уведомление",
        "priority": "normal"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_telegram_bot.send_message.assert_called_once()

def test_send_notification_telegram_error(mock_telegram_bot, mock_redis):
    """Тест обработки ошибки при отправке уведомления."""
    mock_telegram_bot.send_message.side_effect = TelegramError("Telegram API Error")
    
    notification_data = {
        "chat_id": 123456789,
        "message": "Тестовое уведомление",
        "priority": "normal"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 500
    assert "Ошибка при отправке уведомления" in response.json()["detail"]
    mock_redis.setex.assert_called_once()

def test_health_check_success(mock_telegram_bot, mock_redis):
    """Тест успешной проверки здоровья сервиса."""
    mock_telegram_bot.get_me = AsyncMock()
    
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_health_check_redis_error(mock_telegram_bot, mock_redis):
    """Тест проверки здоровья при ошибке Redis."""
    mock_redis.ping.side_effect = Exception("Redis Error")
    
    response = client.get("/api/health/")
    assert response.status_code == 503
    assert "Сервис нездоров" in response.json()["detail"]

def test_health_check_telegram_error(mock_telegram_bot, mock_redis):
    """Тест проверки здоровья при ошибке Telegram API."""
    mock_telegram_bot.get_me.side_effect = TelegramError("Telegram API Error")
    
    response = client.get("/api/health/")
    assert response.status_code == 503
    assert "Сервис нездоров" in response.json()["detail"] 