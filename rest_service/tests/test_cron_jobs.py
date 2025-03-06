import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.models import CronJob, CronJobType, TelegramUser

def test_create_cronjob(client: TestClient, db_session: Session):
    """Тест создания cron-задачи."""
    # Создаем тестового пользователя
    test_user = TelegramUser(telegram_id=123456789, username="test_user")
    db_session.add(test_user)
    db_session.commit()
    
    cronjob_data = {
        "name": "Test CronJob",
        "type": CronJobType.NOTIFICATION,
        "cron_expression": "0 0 * * *",
        "user_id": test_user.id
    }
    
    response = client.post("/api/cronjobs/", json=cronjob_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == cronjob_data["name"]
    assert data["type"] == cronjob_data["type"]
    assert data["cron_expression"] == cronjob_data["cron_expression"]
    assert data["user_id"] == cronjob_data["user_id"]
    
    # Проверяем, что cron-задача создана в базе
    query = select(CronJob).where(CronJob.name == cronjob_data["name"])
    cronjob = db_session.exec(query).first()
    assert cronjob is not None
    assert cronjob.name == cronjob_data["name"]
    assert cronjob.type == cronjob_data["type"]
    assert cronjob.cron_expression == cronjob_data["cron_expression"]
    assert cronjob.user_id == cronjob_data["user_id"]

def test_create_cronjob_nonexistent_user(client: TestClient):
    """Тест создания cron-задачи для несуществующего пользователя."""
    cronjob_data = {
        "name": "Test CronJob",
        "type": CronJobType.NOTIFICATION,
        "cron_expression": "0 0 * * *",
        "user_id": 999999999
    }
    
    response = client.post("/api/cronjobs/", json=cronjob_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"

def test_get_cronjob(client: TestClient, db_session: Session):
    """Тест получения cron-задачи по ID."""
    # Создаем тестового пользователя и cron-задачу
    test_user = TelegramUser(telegram_id=111222333, username="test_user")
    db_session.add(test_user)
    db_session.commit()
    
    test_cronjob = CronJob(
        name="Test Get CronJob",
        type=CronJobType.NOTIFICATION,
        cron_expression="0 0 * * *",
        user_id=test_user.id
    )
    db_session.add(test_cronjob)
    db_session.commit()
    
    response = client.get(f"/api/cronjobs/{test_cronjob.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_cronjob.name
    assert data["type"] == test_cronjob.type
    assert data["cron_expression"] == test_cronjob.cron_expression
    assert data["user_id"] == test_cronjob.user_id

def test_get_nonexistent_cronjob(client: TestClient):
    """Тест получения несуществующей cron-задачи."""
    response = client.get("/api/cronjobs/999999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "CronJob not found"

def test_list_cronjobs(client: TestClient, db_session: Session):
    """Тест получения списка всех cron-задач."""
    # Создаем тестового пользователя
    test_user = TelegramUser(telegram_id=222333444, username="test_user")
    db_session.add(test_user)
    db_session.commit()
    
    # Создаем несколько тестовых cron-задач
    cronjobs = [
        CronJob(
            name="CronJob 1",
            type=CronJobType.NOTIFICATION,
            cron_expression="0 0 * * *",
            user_id=test_user.id
        ),
        CronJob(
            name="CronJob 2",
            type=CronJobType.SCHEDULE,
            cron_expression="0 12 * * *",
            user_id=test_user.id
        )
    ]
    for cronjob in cronjobs:
        db_session.add(cronjob)
    db_session.commit()
    
    response = client.get("/api/cronjobs/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= len(cronjobs)  # Могут быть и другие cron-задачи в базе
    
    # Проверяем, что наши тестовые cron-задачи есть в списке
    cronjob_names = {cronjob["name"] for cronjob in data}
    for test_cronjob in cronjobs:
        assert test_cronjob.name in cronjob_names

def test_update_cronjob(client: TestClient, db_session: Session):
    """Тест обновления cron-задачи."""
    # Создаем тестового пользователя и cron-задачу
    test_user = TelegramUser(telegram_id=333444555, username="test_user")
    db_session.add(test_user)
    db_session.commit()
    
    test_cronjob = CronJob(
        name="Test Update CronJob",
        type=CronJobType.NOTIFICATION,
        cron_expression="0 0 * * *",
        user_id=test_user.id
    )
    db_session.add(test_cronjob)
    db_session.commit()
    
    update_data = {
        "name": "Updated CronJob",
        "type": CronJobType.SCHEDULE,
        "cron_expression": "0 12 * * *"
    }
    
    response = client.patch(f"/api/cronjobs/{test_cronjob.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["type"] == update_data["type"]
    assert data["cron_expression"] == update_data["cron_expression"]
    assert data["user_id"] == test_cronjob.user_id
    
    # Проверяем, что изменения сохранены в базе
    query = select(CronJob).where(CronJob.id == test_cronjob.id)
    updated_cronjob = db_session.exec(query).first()
    assert updated_cronjob.name == update_data["name"]
    assert updated_cronjob.type == update_data["type"]
    assert updated_cronjob.cron_expression == update_data["cron_expression"]

def test_update_nonexistent_cronjob(client: TestClient):
    """Тест обновления несуществующей cron-задачи."""
    update_data = {
        "name": "Updated CronJob",
        "type": CronJobType.SCHEDULE,
        "cron_expression": "0 12 * * *"
    }
    
    response = client.patch("/api/cronjobs/999999999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "CronJob not found"

def test_delete_cronjob(client: TestClient, db_session: Session):
    """Тест удаления cron-задачи."""
    # Создаем тестового пользователя и cron-задачу
    test_user = TelegramUser(telegram_id=444555666, username="test_user")
    db_session.add(test_user)
    db_session.commit()
    
    test_cronjob = CronJob(
        name="Test Delete CronJob",
        type=CronJobType.NOTIFICATION,
        cron_expression="0 0 * * *",
        user_id=test_user.id
    )
    db_session.add(test_cronjob)
    db_session.commit()
    
    response = client.delete(f"/api/cronjobs/{test_cronjob.id}")
    assert response.status_code == 200
    assert response.json()["message"] == f"CronJob with ID {test_cronjob.id} has been deleted"
    
    # Проверяем, что cron-задача удалена из базы
    query = select(CronJob).where(CronJob.id == test_cronjob.id)
    deleted_cronjob = db_session.exec(query).first()
    assert deleted_cronjob is None

def test_delete_nonexistent_cronjob(client: TestClient):
    """Тест удаления несуществующей cron-задачи."""
    response = client.delete("/api/cronjobs/999999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "CronJob not found" 