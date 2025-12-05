from uuid import uuid4

import pytest
from fastapi import status
from httpx import AsyncClient

# Fixtures for test user and client are assumed to be in conftest.py
# e.g., test_user_id, client


@pytest.mark.asyncio
async def test_create_user_fact(client: AsyncClient, test_user_id: int):
    user_id = test_user_id  # Use the ID directly
    fact_data = {"user_id": user_id, "fact": "Test fact about user"}

    response = await client.post(f"/api/users/{user_id}/facts", json=fact_data)

    assert response.status_code == status.HTTP_201_CREATED
    created_fact = response.json()
    assert created_fact["user_id"] == user_id
    assert created_fact["fact"] == fact_data["fact"]
    assert "id" in created_fact
    assert "created_at" in created_fact
    assert "updated_at" in created_fact


@pytest.mark.asyncio
async def test_create_user_fact_user_not_found(client: AsyncClient):
    non_existent_user_id = 99999
    fact_data = {"user_id": non_existent_user_id, "fact": "Fact for non-existent user"}

    response = await client.post(
        f"/api/users/{non_existent_user_id}/facts", json=fact_data
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "User not found"}


@pytest.mark.asyncio
async def test_create_user_fact_id_mismatch(client: AsyncClient, test_user_id: int):
    user_id = test_user_id
    # Need to create a second user to have a valid wrong_user_id
    # This might require adjusting the fixture or test setup
    # For simplicity, let's assume we can just use a different number
    # A better approach might be to create another user in the fixture or test
    wrong_user_id = (
        99998  # Assuming this ID doesn't exist or belongs to another test user
    )
    fact_data = {"user_id": wrong_user_id, "fact": "Mismatch fact"}

    response = await client.post(f"/api/users/{user_id}/facts", json=fact_data)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "User ID in path does not match User ID in payload" in response.json()["detail"]
    )


@pytest.mark.asyncio
async def test_get_user_facts(client: AsyncClient, test_user_id: int):
    user_id = test_user_id
    # Create some facts first
    fact1_data = {"user_id": user_id, "fact": "Fact 1"}
    fact2_data = {"user_id": user_id, "fact": "Fact 2"}
    await client.post(f"/api/users/{user_id}/facts", json=fact1_data)
    await client.post(f"/api/users/{user_id}/facts", json=fact2_data)

    response = await client.get(f"/api/users/{user_id}/facts")

    assert response.status_code == status.HTTP_200_OK
    facts = response.json()
    assert isinstance(facts, list)
    assert len(facts) >= 2
    fact_texts = [f["fact"] for f in facts]
    assert "Fact 1" in fact_texts
    assert "Fact 2" in fact_texts
    for fact in facts:
        assert fact["user_id"] == user_id


@pytest.mark.asyncio
async def test_get_user_facts_user_not_found(client: AsyncClient):
    non_existent_user_id = 99999
    response = await client.get(f"/api/users/{non_existent_user_id}/facts")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "User not found"}


@pytest.mark.asyncio
async def test_delete_user_fact(client: AsyncClient, test_user_id: int):
    user_id = test_user_id
    fact_data = {"user_id": user_id, "fact": "Fact to be deleted"}
    create_response = await client.post(f"/api/users/{user_id}/facts", json=fact_data)
    assert create_response.status_code == status.HTTP_201_CREATED
    fact_id = create_response.json()["id"]

    delete_response = await client.delete(f"/api/facts/{fact_id}")

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    # Verify it's actually deleted
    get_response = await client.get(f"/api/users/{user_id}/facts")
    assert get_response.status_code == status.HTTP_200_OK
    facts_after_delete = get_response.json()
    fact_ids_after_delete = [f["id"] for f in facts_after_delete]
    assert fact_id not in fact_ids_after_delete


@pytest.mark.asyncio
async def test_delete_user_fact_not_found(client: AsyncClient):
    non_existent_fact_id = str(uuid4())

    delete_response = await client.delete(f"/api/facts/{non_existent_fact_id}")

    assert delete_response.status_code == status.HTTP_404_NOT_FOUND
    assert delete_response.json() == {"detail": "Fact not found"}
