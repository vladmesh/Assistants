import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.models.assistant import Assistant, AssistantType

def test_create_assistant(client: TestClient, db_session: Session):
    """Тест создания ассистента."""
    assistant_data = {
        "name": "Test Assistant",
        "is_secretary": False,
        "model": "gpt-4",
        "instructions": "You are a helpful assistant",
        "assistant_type": AssistantType.LLM.value
    }
    
    response = client.post("/api/assistants/", json=assistant_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == assistant_data["name"]
    assert data["model"] == assistant_data["model"]
    assert data["assistant_type"] == assistant_data["assistant_type"]
    
    # Проверяем, что ассистент создан в базе
    query = select(Assistant).where(Assistant.name == assistant_data["name"])
    assistant = db_session.exec(query).first()
    assert assistant is not None
    assert assistant.name == assistant_data["name"]
    assert assistant.model == assistant_data["model"]

def test_create_assistant_with_openai(client: TestClient, db_session: Session):
    """Тест создания ассистента с OpenAI API."""
    assistant_data = {
        "name": "OpenAI Assistant",
        "is_secretary": True,
        "model": "gpt-4",
        "instructions": "You are a secretary assistant",
        "assistant_type": AssistantType.OPENAI_API.value,
        "openai_assistant_id": "asst_123456"
    }
    
    response = client.post("/api/assistants/", json=assistant_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == assistant_data["name"]
    assert data["openai_assistant_id"] == assistant_data["openai_assistant_id"]
    
    # Проверяем в базе
    query = select(Assistant).where(Assistant.name == assistant_data["name"])
    assistant = db_session.exec(query).first()
    assert assistant is not None
    assert assistant.openai_assistant_id == assistant_data["openai_assistant_id"]

def test_get_assistant(client: TestClient, db_session: Session):
    """Тест получения ассистента по ID."""
    # Создаем тестового ассистента
    test_assistant = Assistant(
        name="Test Get Assistant",
        model="gpt-4",
        instructions="Test instructions",
        assistant_type=AssistantType.LLM
    )
    db_session.add(test_assistant)
    db_session.commit()
    
    response = client.get(f"/api/assistants/{test_assistant.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == test_assistant.name
    assert data["model"] == test_assistant.model

def test_get_nonexistent_assistant(client: TestClient):
    """Тест получения несуществующего ассистента."""
    response = client.get("/api/assistants/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Assistant not found"

def test_list_assistants(client: TestClient, db_session: Session):
    """Тест получения списка всех ассистентов."""
    # Создаем несколько тестовых ассистентов
    assistants = [
        Assistant(
            name=f"Test Assistant {i}",
            model="gpt-4",
            instructions=f"Test instructions {i}",
            assistant_type=AssistantType.LLM
        )
        for i in range(3)
    ]
    for assistant in assistants:
        db_session.add(assistant)
    db_session.commit()
    
    response = client.get("/api/assistants/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= len(assistants)
    
    # Проверяем, что наши тестовые ассистенты есть в списке
    assistant_names = {assistant["name"] for assistant in data}
    for test_assistant in assistants:
        assert test_assistant.name in assistant_names

def test_update_assistant(client: TestClient, db_session: Session):
    """Тест обновления ассистента."""
    # Создаем тестового ассистента
    test_assistant = Assistant(
        name="Test Update Assistant",
        model="gpt-4",
        instructions="Initial instructions",
        assistant_type=AssistantType.LLM
    )
    db_session.add(test_assistant)
    db_session.commit()
    
    update_data = {
        "name": "Updated Assistant",
        "instructions": "Updated instructions",
        "is_active": False
    }
    
    response = client.put(f"/api/assistants/{test_assistant.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["instructions"] == update_data["instructions"]
    assert data["is_active"] == update_data["is_active"]
    
    # Проверяем в базе
    query = select(Assistant).where(Assistant.id == test_assistant.id)
    assistant = db_session.exec(query).first()
    assert assistant.name == update_data["name"]
    assert assistant.instructions == update_data["instructions"]
    assert assistant.is_active == update_data["is_active"]

def test_delete_assistant(client: TestClient, db_session: Session):
    """Тест удаления ассистента."""
    # Создаем тестового ассистента
    test_assistant = Assistant(
        name="Test Delete Assistant",
        model="gpt-4",
        instructions="Test instructions",
        assistant_type=AssistantType.LLM
    )
    db_session.add(test_assistant)
    db_session.commit()
    
    response = client.delete(f"/api/assistants/{test_assistant.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Assistant deleted successfully"
    
    # Проверяем, что ассистент удален из базы
    query = select(Assistant).where(Assistant.id == test_assistant.id)
    assistant = db_session.exec(query).first()
    assert assistant is None 