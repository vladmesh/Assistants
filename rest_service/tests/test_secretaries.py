from uuid import UUID

import pytest
from httpx import AsyncClient
from models.assistant import Assistant
from models.user_secretary import UserSecretaryLink
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# Assuming you have fixtures for AsyncClient (client) and AsyncSession (db_session)
# and potentially fixtures to create a test user and a secretary assistant.


@pytest.mark.asyncio
async def test_list_secretaries(client: AsyncClient, db_session: AsyncSession):
    """Test listing all available secretaries."""
    # Ensure at least one secretary exists (create if needed via fixture or here)
    secretary = Assistant(
        name="Test Secretary",
        is_secretary=True,
        model="gpt-test",
        instructions="Test instructions",
        assistant_type="llm",
    )
    db_session.add(secretary)
    await db_session.commit()
    await db_session.refresh(secretary)

    response = await client.get("/api/secretaries/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert any(item["id"] == str(secretary.id) for item in data)
    assert all(item["is_secretary"] for item in data)


@pytest.mark.asyncio
async def test_list_active_user_secretary_assignments(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_id: int,
    test_secretary_id: UUID,
):
    """Test listing active user-secretary assignments."""
    # Create an active assignment using the IDs from fixtures
    active_link = UserSecretaryLink(
        user_id=test_user_id,
        secretary_id=test_secretary_id,
        is_active=True,
    )
    # Create an inactive assignment (should not be returned)
    inactive_link = UserSecretaryLink(
        user_id=test_user_id,  # Same user, different link
        secretary_id=test_secretary_id,
        is_active=False,  # Inactive
    )
    db_session.add_all([active_link, inactive_link])
    await db_session.commit()
    # No need to refresh link here

    response = await client.get("/api/user-secretaries/assignments")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, list)
    assert len(data) == 1  # Only the active link should be returned
    assignment = data[0]
    assert assignment["user_id"] == test_user_id
    assert assignment["secretary_id"] == str(test_secretary_id)
    # Check if updated_at is a valid datetime string (basic check)
    assert isinstance(assignment["updated_at"], str)


@pytest.mark.asyncio
async def test_list_active_user_secretary_assignments_empty(client: AsyncClient):
    """Test listing assignments when none are active."""
    response = await client.get("/api/user-secretaries/assignments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0
