import asyncio
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

# Assuming your schemas are importable like this
from shared_models.api_schemas.user_summary import (
    UserSummaryCreateUpdate,
    UserSummaryRead,
)

pytestmark = pytest.mark.asyncio


async def test_create_user_summary(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test creating a new user summary."""
    summary_data = UserSummaryCreateUpdate(summary_text="First summary text")
    url = f"/api/user-summaries/{test_user_id}/{test_secretary_id}"

    response = await client.post(url, json=summary_data.model_dump())

    assert response.status_code == 200
    response_data = response.json()
    # Validate response against the Read schema
    summary_read = UserSummaryRead(**response_data)
    assert summary_read.summary_text == summary_data.summary_text
    assert summary_read.created_at is not None
    assert summary_read.updated_at is not None
    # assert summary_read.created_at == summary_read.updated_at # First creation


async def test_create_multiple_summaries_creates_history(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test that posting multiple summaries creates separate history entries."""
    summary1_text = "Summary version 1"
    summary2_text = "Summary version 2"
    url = f"/api/user-summaries/{test_user_id}/{test_secretary_id}"

    # Post first summary
    response1 = await client.post(url, json={"summary_text": summary1_text})
    assert response1.status_code == 200
    data1 = UserSummaryRead(**response1.json())
    assert data1.summary_text == summary1_text

    # Wait briefly to ensure distinct timestamps if resolution is low
    await asyncio.sleep(0.01)

    # Post second summary
    response2 = await client.post(url, json={"summary_text": summary2_text})
    assert response2.status_code == 200
    data2 = UserSummaryRead(**response2.json())
    assert data2.summary_text == summary2_text

    # Check they are different records and timestamps updated
    assert data1.id != data2.id
    assert data2.created_at > data1.created_at
    assert data2.updated_at > data1.updated_at


async def test_get_latest_user_summary(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test retrieving the latest user summary."""
    summary1_text = "Old summary"
    summary2_text = "Newest summary"
    post_url = f"/api/user-summaries/{test_user_id}/{test_secretary_id}"
    get_url = f"/api/user-summaries/{test_user_id}/{test_secretary_id}/latest"

    # Create two summaries
    await client.post(post_url, json={"summary_text": summary1_text})
    await asyncio.sleep(0.01)  # Ensure timestamp difference
    await client.post(post_url, json={"summary_text": summary2_text})

    # Get the latest summary
    response = await client.get(get_url)
    assert response.status_code == 200
    response_data = response.json()

    assert response_data is not None
    latest_summary = UserSummaryRead(**response_data)
    assert latest_summary.summary_text == summary2_text


async def test_get_latest_user_summary_not_found(
    client: AsyncClient, test_user_id: int, test_secretary_id: UUID
):
    """Test retrieving the latest summary when none exist."""
    # Use existing user/secretary but ensure no summaries are present (fixtures handle cleanup)
    get_url = f"/api/user-summaries/{test_user_id}/{test_secretary_id}/latest"

    response = await client.get(get_url)
    assert response.status_code == 200
    # Response body should be null/None for Optional response model
    assert response.json() is None


async def test_create_summary_user_not_found(
    client: AsyncClient, test_secretary_id: UUID
):
    """Test creating a summary for a non-existent user."""
    non_existent_user_id = 99999
    url = f"/api/user-summaries/{non_existent_user_id}/{test_secretary_id}"
    summary_data = UserSummaryCreateUpdate(summary_text="Test")

    response = await client.post(url, json=summary_data.model_dump())
    assert response.status_code == 404


async def test_create_summary_secretary_not_found(
    client: AsyncClient, test_user_id: int
):
    """Test creating a summary for a non-existent secretary."""
    non_existent_secretary_id = uuid4()  # Random UUID
    url = f"/api/user-summaries/{test_user_id}/{non_existent_secretary_id}"
    summary_data = UserSummaryCreateUpdate(summary_text="Test")

    response = await client.post(url, json=summary_data.model_dump())
    assert response.status_code == 404
