import pytest
from datetime import datetime, timedelta, UTC
from app.models import TaskStatus

def test_create_task(client, test_user):
    # Создаем задачу
    task_data = {
        "title": "Test Task",
        "description": "Test Description",
        "user_id": test_user.id,
        "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
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

def test_get_task_by_id(client, test_user):
    # Создаем задачу
    task_data = {
        "title": "Test Task",
        "description": "Test Description",
        "user_id": test_user.id,
        "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "status": "Активно"
    }
    
    create_response = client.post("/api/tasks/", json=task_data)
    assert create_response.status_code == 200
    task_id = create_response.json()["id"]
    
    # Получаем задачу по ID
    response = client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == task_id
    assert data["title"] == "Test Task"

def test_get_nonexistent_task(client):
    # Пытаемся получить несуществующую задачу
    response = client.get("/api/tasks/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"

def test_get_active_tasks(client, test_user):
    # Создаем несколько задач с разными статусами
    tasks = [
        {
            "title": "Active Task",
            "description": "This is active",
            "user_id": test_user.id,
            "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "status": "Активно"
        },
        {
            "title": "Completed Task",
            "description": "This is completed",
            "user_id": test_user.id,
            "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "status": "Готово"
        }
    ]
    
    for task_data in tasks:
        response = client.post("/api/tasks/", json=task_data)
        assert response.status_code == 200
    
    # Получаем активные задачи
    response = client.get(f"/api/tasks/active/{test_user.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "Active Task"
    assert data[0]["status"] == "Активно"

def test_update_task(client, test_user):
    # Создаем задачу
    task_data = {
        "title": "Original Title",
        "description": "Original Description",
        "user_id": test_user.id,
        "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "status": "Активно"
    }
    
    create_response = client.post("/api/tasks/", json=task_data)
    assert create_response.status_code == 200
    task_id = create_response.json()["id"]
    
    # Обновляем задачу
    update_data = {
        "title": "Updated Title",
        "status": "Готово"
    }
    
    response = client.patch(f"/api/tasks/{task_id}", json=update_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == task_id
    assert data["title"] == "Updated Title"
    assert data["status"] == "Готово"
    assert data["description"] == "Original Description"  # Не должно измениться

def test_update_nonexistent_task(client):
    # Пытаемся обновить несуществующую задачу
    update_data = {
        "title": "Updated Title",
        "status": "Готово"
    }
    
    response = client.patch("/api/tasks/999999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found" 