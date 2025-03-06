import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.models import TelegramUser

def test_create_user(client: TestClient, db_session: Session):
    """Тест создания пользователя."""
    user_data = {
        "telegram_id": 123456789,
        "username": "test_user"
    }
    
    response = client.post("/api/users/", json=user_data)
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == user_data["telegram_id"]
    assert data["username"] == user_data["username"]
    
    # Проверяем, что пользователь создан в базе
    query = select(TelegramUser).where(TelegramUser.telegram_id == user_data["telegram_id"])
    user = db_session.exec(query).first()
    assert user is not None
    assert user.telegram_id == user_data["telegram_id"]
    assert user.username == user_data["username"]

def test_create_user_without_username(client: TestClient, db_session: Session):
    """Тест создания пользователя без username."""
    user_data = {
        "telegram_id": 987654321
    }
    
    response = client.post("/api/users/", json=user_data)
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == user_data["telegram_id"]
    assert data["username"] is None
    
    # Проверяем, что пользователь создан в базе
    query = select(TelegramUser).where(TelegramUser.telegram_id == user_data["telegram_id"])
    user = db_session.exec(query).first()
    assert user is not None
    assert user.telegram_id == user_data["telegram_id"]
    assert user.username is None

def test_get_user(client: TestClient, db_session: Session):
    """Тест получения пользователя по telegram_id."""
    # Создаем тестового пользователя
    test_user = TelegramUser(telegram_id=111222333, username="test_get_user")
    db_session.add(test_user)
    db_session.commit()
    
    response = client.get(f"/api/users/?telegram_id={test_user.telegram_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == test_user.telegram_id
    assert data["username"] == test_user.username

def test_get_nonexistent_user(client: TestClient):
    """Тест получения несуществующего пользователя."""
    response = client.get("/api/users/?telegram_id=999999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_list_users(client: TestClient, db_session: Session):
    """Тест получения списка всех пользователей."""
    # Создаем несколько тестовых пользователей
    users = [
        TelegramUser(telegram_id=111111111, username="user1"),
        TelegramUser(telegram_id=222222222, username="user2"),
        TelegramUser(telegram_id=333333333, username="user3")
    ]
    for user in users:
        db_session.add(user)
    db_session.commit()
    
    response = client.get("/api/users/all/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= len(users)  # Могут быть и другие пользователи в базе
    
    # Проверяем, что наши тестовые пользователи есть в списке
    user_ids = {user["telegram_id"] for user in data}
    for test_user in users:
        assert test_user.telegram_id in user_ids 