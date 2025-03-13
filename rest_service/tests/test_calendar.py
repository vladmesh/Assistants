import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.models import TelegramUser, CalendarCredentials
from sqlmodel import Session, select

def test_update_calendar_token(client: TestClient, test_user: TelegramUser, db_session: Session):
    """Test updating user's Google Calendar token"""
    access_token = "test_access_token"
    refresh_token = "test_refresh_token"
    token_expiry = datetime.utcnow() + timedelta(hours=1)
    
    response = client.put(
        f"/api/calendar/user/{test_user.id}/token",
        params={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expiry": token_expiry.isoformat()
        }
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Token updated successfully"
    
    # Проверяем, что токен сохранился в базе
    credentials = db_session.exec(select(CalendarCredentials).where(
        CalendarCredentials.user_id == test_user.id
    )).first()
    assert credentials is not None
    assert credentials.access_token == access_token
    assert credentials.refresh_token == refresh_token
    assert abs((credentials.token_expiry - token_expiry).total_seconds()) < 1

def test_update_calendar_token_user_not_found(client: TestClient):
    """Test updating token for non-existent user"""
    response = client.put(
        "/api/calendar/user/999999/token",
        params={
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_expiry": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found" 