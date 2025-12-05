import asyncio
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

# Assuming your schemas are importable like this
from shared_models.api_schemas.user_summary import (
    UserSummaryRead,
)

pytestmark = pytest.mark.asyncio


async def test_create_user_summary(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test creating a new user summary."""
    summary_data = {
        "summary_text": "First summary text",
        "user_id": test_user_id,
        "assistant_id": str(test_secretary_id),
    }

    response = await client.post("/api/user-summaries/", json=summary_data)

    assert response.status_code == 201  # Changed to 201 as per the endpoint definition
    response_data = response.json()
    # Validate response against the Read schema
    summary_read = UserSummaryRead(**response_data)
    assert summary_read.summary_text == summary_data["summary_text"]
    assert summary_read.created_at is not None
    assert summary_read.updated_at is not None
    # assert summary_read.created_at == summary_read.updated_at # First creation


async def test_create_multiple_summaries_creates_history(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test that posting multiple summaries creates separate history entries."""
    summary1_text = "Summary version 1"
    summary2_text = "Summary version 2"

    # Post first summary
    summary1_data = {
        "summary_text": summary1_text,
        "user_id": test_user_id,
        "assistant_id": str(test_secretary_id),
    }
    response1 = await client.post("/api/user-summaries/", json=summary1_data)
    assert response1.status_code == 201
    data1 = UserSummaryRead(**response1.json())
    assert data1.summary_text == summary1_data["summary_text"]

    # Wait briefly to ensure distinct timestamps if resolution is low
    await asyncio.sleep(0.01)

    # Post second summary
    summary2_data = {
        "summary_text": summary2_text,
        "user_id": test_user_id,
        "assistant_id": str(test_secretary_id),
    }
    response2 = await client.post("/api/user-summaries/", json=summary2_data)
    assert response2.status_code == 201
    data2 = UserSummaryRead(**response2.json())
    assert data2.summary_text == summary2_data["summary_text"]

    # Check they are different records and timestamps updated
    assert data1.id != data2.id
    assert data2.created_at > data1.created_at
    assert data2.updated_at > data1.updated_at


async def test_get_latest_user_summary(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test retrieving the latest user summary."""
    # Create two summaries
    summary1_data = {
        "summary_text": "Old summary",
        "user_id": test_user_id,
        "assistant_id": str(test_secretary_id),
    }
    summary2_data = {
        "summary_text": "Newest summary",
        "user_id": test_user_id,
        "assistant_id": str(test_secretary_id),
    }

    # Create summaries
    await client.post("/api/user-summaries/", json=summary1_data)
    await asyncio.sleep(0.01)  # Ensure timestamp difference
    await client.post("/api/user-summaries/", json=summary2_data)

    # Get the latest summary
    response = await client.get(
        "/api/user-summaries/latest/",
        params={"user_id": test_user_id, "assistant_id": str(test_secretary_id)},
    )
    assert response.status_code == 200
    response_data = response.json()

    assert response_data is not None
    latest_summary = UserSummaryRead(**response_data)
    assert latest_summary.summary_text == "Newest summary"


async def test_get_latest_user_summary_not_found(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test retrieving the latest summary when none exist."""
    # Ensure no summaries exist for this user/secretary before request.
    response = await client.get(
        "/api/user-summaries/latest/",
        params={"user_id": test_user_id, "assistant_id": str(test_secretary_id)},
    )
    assert response.status_code == 200
    # Response body should be null/None for Optional response model
    assert response.json() is None


async def test_create_summary_user_not_found(
    client: AsyncClient, test_secretary_id: UUID
):
    """Test creating a summary for a non-existent user."""
    non_existent_user_id = 99999
    summary_data = {
        "summary_text": "Test",
        "user_id": non_existent_user_id,
        "assistant_id": str(test_secretary_id),
    }

    response = await client.post("/api/user-summaries/", json=summary_data)
    assert response.status_code == 404


async def test_create_summary_secretary_not_found(
    client: AsyncClient, test_user_id: int
):
    """Test creating a summary for a non-existent secretary."""
    non_existent_secretary_id = uuid4()  # Random UUID
    summary_data = {
        "summary_text": "Test",
        "user_id": test_user_id,
        "assistant_id": str(non_existent_secretary_id),
    }

    response = await client.post("/api/user-summaries/", json=summary_data)
    assert response.status_code == 404
