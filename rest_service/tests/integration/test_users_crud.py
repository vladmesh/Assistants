# rest_service/tests/integration/test_users_crud.py
"""Integration tests for Users API endpoints with real database."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    """Test creating a new user via API."""
    response = await client.post(
        "/api/users/",
        json={"telegram_id": 123456789, "username": "integration_test_user"},
    )

    assert response.status_code == 201  # HTTP 201 Created
    data = response.json()
    assert data["telegram_id"] == 123456789
    assert data["username"] == "integration_test_user"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_user_duplicate_telegram_id(client: AsyncClient):
    """Test that creating user with duplicate telegram_id fails."""
    # Create first user
    await client.post(
        "/api/users/",
        json={"telegram_id": 111222333, "username": "first_user"},
    )

    # Try to create second user with same telegram_id
    response = await client.post(
        "/api/users/",
        json={"telegram_id": 111222333, "username": "second_user"},
    )

    assert response.status_code == 409  # HTTP 409 Conflict
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient):
    """Test getting user by internal ID."""
    # Create user first
    create_response = await client.post(
        "/api/users/",
        json={"telegram_id": 987654321, "username": "get_test_user"},
    )
    user_id = create_response.json()["id"]

    # Get user by ID
    response = await client.get(f"/api/users/{user_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["telegram_id"] == 987654321


@pytest.mark.asyncio
async def test_get_user_by_telegram_id(client: AsyncClient):
    """Test getting user by telegram_id."""
    # Create user first
    await client.post(
        "/api/users/",
        json={"telegram_id": 555666777, "username": "telegram_lookup_user"},
    )

    # Get user by telegram_id
    response = await client.get(
        "/api/users/by-telegram-id/",
        params={"telegram_id": 555666777},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["telegram_id"] == 555666777
    assert data["username"] == "telegram_lookup_user"


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient):
    """Test getting non-existent user returns 404."""
    response = await client.get("/api/users/99999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient):
    """Test updating user data."""
    # Create user
    create_response = await client.post(
        "/api/users/",
        json={"telegram_id": 444555666, "username": "original_name"},
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    # Update user
    response = await client.patch(
        f"/api/users/{user_id}",
        json={"username": "updated_name", "timezone": "Europe/Moscow"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "updated_name"
    # timezone may or may not be in the response depending on schema
    assert "id" in data


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient):
    """Test listing all users with pagination."""
    # Create a few users
    for i in range(3):
        await client.post(
            "/api/users/",
            json={"telegram_id": 100000 + i, "username": f"list_user_{i}"},
        )

    # List users
    response = await client.get("/api/users/", params={"limit": 10})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3


@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient):
    """Test deleting a user."""
    # Create user
    create_response = await client.post(
        "/api/users/",
        json={"telegram_id": 999888777, "username": "delete_me"},
    )
    assert create_response.status_code == 201
    user_id = create_response.json()["id"]

    # Delete user
    response = await client.delete(f"/api/users/{user_id}")
    assert response.status_code == 204  # HTTP 204 No Content

    # Verify user is gone
    get_response = await client.get(f"/api/users/{user_id}")
    assert get_response.status_code == 404
