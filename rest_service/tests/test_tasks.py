import pytest
from datetime import datetime, timedelta
from app.models import TaskStatus

def test_create_task(client, test_user):
    # Создаем задачу
    task_data = {
        "title": "Test Task",
        "description": "Test Description",
        "user_id": test_user.id,
        "due_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        "status": "Активно"
    }
    
    response = client.post("/api/tasks/", json=task_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["description"] == "Test Description"
    assert data["status"] == "Активно"
    assert data["user_id"] == test_user.id

def test_get_tasks(client, test_user):
    # Получаем список задач пользователя
    response = client.get(f"/api/tasks/?user_id={test_user.telegram_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list) 