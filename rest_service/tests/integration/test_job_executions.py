"""Integration tests for job_executions API."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

BASE_URL = "/api/job-executions"


class TestJobExecutionsAPI:
    """Integration tests for job executions endpoints."""

    @pytest.mark.asyncio
    async def test_create_job_execution(self, client: AsyncClient):
        """Test creating a new job execution record."""
        scheduled_at = datetime.now(UTC)
        response = await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "reminder_test-123",
                "job_name": "Test Reminder",
                "job_type": "reminder",
                "scheduled_at": scheduled_at.isoformat(),
                "user_id": 42,
                "reminder_id": 1,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == "reminder_test-123"
        assert data["job_name"] == "Test Reminder"
        assert data["job_type"] == "reminder"
        assert data["status"] == "scheduled"
        assert data["user_id"] == 42
        assert data["reminder_id"] == 1
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_job_execution_minimal(self, client: AsyncClient):
        """Test creating job execution with only required fields."""
        scheduled_at = datetime.now(UTC)
        response = await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "update_reminders",
                "job_name": "Update Reminders Job",
                "job_type": "update_reminders",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] is None
        assert data["reminder_id"] is None

    @pytest.mark.asyncio
    async def test_get_job_execution(self, client: AsyncClient):
        """Test getting a specific job execution by ID."""
        # First create a job
        scheduled_at = datetime.now(UTC)
        create_response = await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "test_job",
                "job_name": "Test Job",
                "job_type": "reminder",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        job_id = create_response.json()["id"]

        # Then get it
        response = await client.get(f"{BASE_URL}/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["job_name"] == "Test Job"

    @pytest.mark.asyncio
    async def test_get_job_execution_not_found(self, client: AsyncClient):
        """Test getting nonexistent job execution returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"{BASE_URL}/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_job_execution_full_lifecycle(self, client: AsyncClient):
        """Test complete job execution lifecycle: create -> start -> complete."""
        # 1. Create
        scheduled_at = datetime.now(UTC)
        create_response = await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "lifecycle_test",
                "job_name": "Lifecycle Test Job",
                "job_type": "reminder",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]
        assert create_response.json()["status"] == "scheduled"

        # 2. Start
        start_response = await client.patch(f"{BASE_URL}/{job_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "running"
        assert start_response.json()["started_at"] is not None

        # 3. Complete
        complete_response = await client.patch(
            f"{BASE_URL}/{job_id}/complete",
            json={"result": '{"messages_sent": 1}'},
        )
        assert complete_response.status_code == 200
        data = complete_response.json()
        assert data["status"] == "completed"
        assert data["finished_at"] is not None
        assert data["duration_ms"] is not None
        assert data["result"] == '{"messages_sent": 1}'

    @pytest.mark.asyncio
    async def test_job_execution_failure_flow(self, client: AsyncClient):
        """Test job execution failure: create -> start -> fail."""
        # 1. Create
        scheduled_at = datetime.now(UTC)
        create_response = await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "failure_test",
                "job_name": "Failure Test Job",
                "job_type": "reminder",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        job_id = create_response.json()["id"]

        # 2. Start
        await client.patch(f"{BASE_URL}/{job_id}/start")

        # 3. Fail
        fail_response = await client.patch(
            f"{BASE_URL}/{job_id}/fail",
            json={
                "error": "Connection refused",
                "error_traceback": "Traceback:\n  File ...",
            },
        )
        assert fail_response.status_code == 200
        data = fail_response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Connection refused"
        assert "Traceback" in data["error_traceback"]
        assert data["finished_at"] is not None

    @pytest.mark.asyncio
    async def test_list_job_executions(self, client: AsyncClient):
        """Test listing job executions."""
        # Create several jobs
        scheduled_at = datetime.now(UTC)
        for i in range(3):
            await client.post(
                f"{BASE_URL}/",
                json={
                    "job_id": f"list_test_{i}",
                    "job_name": f"List Test Job {i}",
                    "job_type": "reminder",
                    "scheduled_at": scheduled_at.isoformat(),
                },
            )

        response = await client.get(f"{BASE_URL}/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

    @pytest.mark.asyncio
    async def test_list_job_executions_filter_by_type(self, client: AsyncClient):
        """Test filtering job executions by type."""
        scheduled_at = datetime.now(UTC)

        # Create jobs of different types
        await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "reminder_1",
                "job_name": "Reminder 1",
                "job_type": "reminder",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "memory_1",
                "job_name": "Memory 1",
                "job_type": "memory_extraction",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )

        # Filter by reminder type
        response = await client.get(f"{BASE_URL}/?job_type=reminder")

        assert response.status_code == 200
        data = response.json()
        for job in data:
            assert job["job_type"] == "reminder"

    @pytest.mark.asyncio
    async def test_list_job_executions_filter_by_status(self, client: AsyncClient):
        """Test filtering job executions by status."""
        scheduled_at = datetime.now(UTC)

        # Create and complete a job
        create_resp = await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "status_filter_test",
                "job_name": "Status Filter Test",
                "job_type": "reminder",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        job_id = create_resp.json()["id"]
        await client.patch(f"{BASE_URL}/{job_id}/start")
        await client.patch(f"{BASE_URL}/{job_id}/complete")

        # Filter by completed status
        response = await client.get(f"{BASE_URL}/?status=completed")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for job in data:
            assert job["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_job_stats(self, client: AsyncClient):
        """Test getting job statistics."""
        scheduled_at = datetime.now(UTC)

        # Create some jobs with different statuses
        for i in range(2):
            create_resp = await client.post(
                f"{BASE_URL}/",
                json={
                    "job_id": f"stats_test_{i}",
                    "job_name": f"Stats Test {i}",
                    "job_type": "reminder",
                    "scheduled_at": scheduled_at.isoformat(),
                },
            )
            job_id = create_resp.json()["id"]
            await client.patch(f"{BASE_URL}/{job_id}/start")
            await client.patch(f"{BASE_URL}/{job_id}/complete")

        # Create a failed job
        create_resp = await client.post(
            f"{BASE_URL}/",
            json={
                "job_id": "stats_test_failed",
                "job_name": "Stats Test Failed",
                "job_type": "reminder",
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        job_id = create_resp.json()["id"]
        await client.patch(f"{BASE_URL}/{job_id}/start")
        await client.patch(
            f"{BASE_URL}/{job_id}/fail",
            json={"error": "Test error"},
        )

        response = await client.get(f"{BASE_URL}/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "completed" in data
        assert "failed" in data
        assert "running" in data
        assert "scheduled" in data
        assert "avg_duration_ms" in data
        assert "by_type" in data
        assert data["completed"] >= 2
        assert data["failed"] >= 1

    @pytest.mark.asyncio
    async def test_get_job_stats_custom_hours(self, client: AsyncClient):
        """Test getting job statistics with custom time range."""
        response = await client.get(f"{BASE_URL}/stats?hours=48")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data

    @pytest.mark.asyncio
    async def test_cleanup_old_executions(self, client: AsyncClient):
        """Test cleanup endpoint."""
        response = await client.delete(f"{BASE_URL}/cleanup?days=7")

        assert response.status_code == 200
        data = response.json()
        assert "deleted" in data
        assert isinstance(data["deleted"], int)

    @pytest.mark.asyncio
    async def test_start_nonexistent_job(self, client: AsyncClient):
        """Test starting nonexistent job returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(f"{BASE_URL}/{fake_id}/start")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_complete_nonexistent_job(self, client: AsyncClient):
        """Test completing nonexistent job returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(f"{BASE_URL}/{fake_id}/complete")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_fail_nonexistent_job(self, client: AsyncClient):
        """Test failing nonexistent job returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"{BASE_URL}/{fake_id}/fail",
            json={"error": "Test error"},
        )

        assert response.status_code == 404
