import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)

@pytest.fixture
def mock_telegram_bot():
    with patch("app.main.bot") as mock_bot:
        mock_bot.send_message = AsyncMock()
        yield mock_bot

@pytest.fixture
def mock_redis():
    with patch("app.main.redis_client") as mock_redis:
        mock_redis.ping = lambda: True
        mock_redis.setex = lambda *args: None
        yield mock_redis

def test_normal_priority(mock_telegram_bot):
    """Тест отправки уведомления с нормальным приоритетом."""
    notification_data = {
        "chat_id": 123456789,
        "message": "Тестовое уведомление",
        "priority": "normal"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 200
    mock_telegram_bot.send_message.assert_called_once()

def test_high_priority(mock_telegram_bot):
    """Тест отправки уведомления с высоким приоритетом."""
    notification_data = {
        "chat_id": 123456789,
        "message": "Срочное уведомление!",
        "priority": "high"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 200
    mock_telegram_bot.send_message.assert_called_once()

def test_low_priority(mock_telegram_bot):
    """Тест отправки уведомления с низким приоритетом."""
    notification_data = {
        "chat_id": 123456789,
        "message": "Несрочное уведомление",
        "priority": "low"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 200
    mock_telegram_bot.send_message.assert_called_once()

def test_invalid_priority(mock_telegram_bot):
    """Тест отправки уведомления с неверным приоритетом."""
    notification_data = {
        "chat_id": 123456789,
        "message": "Тестовое уведомление",
        "priority": "invalid"
    }
    
    response = client.post("/api/notify/", json=notification_data)
    assert response.status_code == 422  # Validation error 