"""Unit tests for job_execution CRUD operations."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture
def mock_session():
    """Create mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_job_execution():
    """Create a sample job execution for tests."""
    from models.job_execution import JobExecution, JobStatus

    return JobExecution(
        id=uuid4(),
        job_id="reminder_test-123",
        job_name="Test Reminder",
        job_type="reminder",
        status=JobStatus.SCHEDULED,
        scheduled_at=datetime.now(UTC),
        user_id=42,
        reminder_id=1,
    )


class TestGetJobExecution:
    """Tests for get function."""

    @pytest.mark.asyncio
    async def test_job_found(self, mock_session, sample_job_execution):
        """Test getting job execution when exists."""
        from crud.job_execution import get

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job_execution
        mock_session.execute.return_value = mock_result

        result = await get(mock_session, sample_job_execution.id)

        assert result == sample_job_execution

    @pytest.mark.asyncio
    async def test_job_not_found(self, mock_session):
        """Test getting job execution when not exists."""
        from crud.job_execution import get

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await get(mock_session, uuid4())

        assert result is None


class TestCreateJobExecution:
    """Tests for create function."""

    @pytest.mark.asyncio
    async def test_create_job_execution_success(self, mock_session):
        """Test creating job execution successfully."""
        from crud.job_execution import create
        from models.job_execution import JobStatus

        scheduled_at = datetime.now(UTC)

        with patch("crud.job_execution.JobExecution") as MockJobExecution:
            mock_job = MagicMock()
            mock_job.status = JobStatus.SCHEDULED
            MockJobExecution.return_value = mock_job

            result = await create(
                mock_session,
                job_id="reminder_abc",
                job_name="Test Job",
                job_type="reminder",
                scheduled_at=scheduled_at,
                user_id=42,
                reminder_id=1,
            )

            assert result == mock_job
            mock_session.add.assert_called_once_with(mock_job)
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_job)

            # Verify JobExecution was created with correct params
            call_kwargs = MockJobExecution.call_args[1]
            assert call_kwargs["job_id"] == "reminder_abc"
            assert call_kwargs["job_name"] == "Test Job"
            assert call_kwargs["job_type"] == "reminder"
            assert call_kwargs["scheduled_at"] == scheduled_at
            assert call_kwargs["user_id"] == 42
            assert call_kwargs["reminder_id"] == 1
            assert call_kwargs["status"] == JobStatus.SCHEDULED

    @pytest.mark.asyncio
    async def test_create_job_execution_without_optional_fields(self, mock_session):
        """Test creating job execution without user_id and reminder_id."""
        from crud.job_execution import create

        scheduled_at = datetime.now(UTC)

        with patch("crud.job_execution.JobExecution") as MockJobExecution:
            mock_job = MagicMock()
            MockJobExecution.return_value = mock_job

            await create(
                mock_session,
                job_id="update_reminders",
                job_name="Update Reminders",
                job_type="update_reminders",
                scheduled_at=scheduled_at,
            )

            call_kwargs = MockJobExecution.call_args[1]
            assert call_kwargs["user_id"] is None
            assert call_kwargs["reminder_id"] is None


class TestStartJobExecution:
    """Tests for start function."""

    @pytest.mark.asyncio
    async def test_start_job_success(self, mock_session, sample_job_execution):
        """Test starting job execution successfully."""
        from crud.job_execution import start
        from models.job_execution import JobStatus

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job_execution
        mock_session.execute.return_value = mock_result

        result = await start(mock_session, sample_job_execution.id)

        assert result == sample_job_execution
        assert sample_job_execution.status == JobStatus.RUNNING
        assert sample_job_execution.started_at is not None
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_job_not_found(self, mock_session):
        """Test starting nonexistent job returns None."""
        from crud.job_execution import start

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await start(mock_session, uuid4())

        assert result is None
        mock_session.add.assert_not_called()


class TestCompleteJobExecution:
    """Tests for complete function."""

    @pytest.mark.asyncio
    async def test_complete_job_success(self, mock_session, sample_job_execution):
        """Test completing job execution successfully."""
        from crud.job_execution import complete
        from models.job_execution import JobStatus

        # Set started_at to calculate duration
        sample_job_execution.started_at = datetime.now(UTC) - timedelta(seconds=5)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job_execution
        mock_session.execute.return_value = mock_result

        result = await complete(
            mock_session, sample_job_execution.id, result='{"success": true}'
        )

        assert result == sample_job_execution
        assert sample_job_execution.status == JobStatus.COMPLETED
        assert sample_job_execution.finished_at is not None
        assert sample_job_execution.duration_ms is not None
        assert sample_job_execution.duration_ms >= 5000  # At least 5 seconds
        assert sample_job_execution.result == '{"success": true}'

    @pytest.mark.asyncio
    async def test_complete_job_without_result(
        self, mock_session, sample_job_execution
    ):
        """Test completing job without result string."""
        from crud.job_execution import complete

        sample_job_execution.started_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job_execution
        mock_session.execute.return_value = mock_result

        result = await complete(mock_session, sample_job_execution.id)

        assert result.result is None

    @pytest.mark.asyncio
    async def test_complete_job_not_started(self, mock_session, sample_job_execution):
        """Test completing job that was never started (no started_at)."""
        from crud.job_execution import complete

        sample_job_execution.started_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job_execution
        mock_session.execute.return_value = mock_result

        result = await complete(mock_session, sample_job_execution.id)

        assert result.duration_ms is None

    @pytest.mark.asyncio
    async def test_complete_job_not_found(self, mock_session):
        """Test completing nonexistent job returns None."""
        from crud.job_execution import complete

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await complete(mock_session, uuid4())

        assert result is None


class TestFailJobExecution:
    """Tests for fail function."""

    @pytest.mark.asyncio
    async def test_fail_job_success(self, mock_session, sample_job_execution):
        """Test failing job execution with error."""
        from crud.job_execution import fail
        from models.job_execution import JobStatus

        sample_job_execution.started_at = datetime.now(UTC) - timedelta(seconds=2)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job_execution
        mock_session.execute.return_value = mock_result

        result = await fail(
            mock_session,
            sample_job_execution.id,
            error="Connection timeout",
            error_traceback="Traceback (most recent call last):\n...",
        )

        assert result == sample_job_execution
        assert sample_job_execution.status == JobStatus.FAILED
        assert sample_job_execution.finished_at is not None
        assert sample_job_execution.duration_ms is not None
        assert sample_job_execution.error == "Connection timeout"
        assert "Traceback" in sample_job_execution.error_traceback

    @pytest.mark.asyncio
    async def test_fail_job_without_traceback(self, mock_session, sample_job_execution):
        """Test failing job without traceback."""
        from crud.job_execution import fail

        sample_job_execution.started_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_job_execution
        mock_session.execute.return_value = mock_result

        result = await fail(mock_session, sample_job_execution.id, error="Simple error")

        assert result.error == "Simple error"
        assert result.error_traceback is None

    @pytest.mark.asyncio
    async def test_fail_job_not_found(self, mock_session):
        """Test failing nonexistent job returns None."""
        from crud.job_execution import fail

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await fail(mock_session, uuid4(), error="Error")

        assert result is None


class TestGetListJobExecutions:
    """Tests for get_list function."""

    @pytest.mark.asyncio
    async def test_get_list_returns_all(self, mock_session):
        """Test getting list without filters."""
        from crud.job_execution import get_list

        mock_jobs = [MagicMock(), MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_jobs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_list(mock_session)

        assert result == mock_jobs

    @pytest.mark.asyncio
    async def test_get_list_with_job_type_filter(self, mock_session):
        """Test filtering by job_type."""
        from crud.job_execution import get_list

        mock_jobs = [MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_jobs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_list(mock_session, job_type="reminder")

        assert result == mock_jobs

    @pytest.mark.asyncio
    async def test_get_list_with_status_filter(self, mock_session):
        """Test filtering by status."""
        from crud.job_execution import get_list
        from models.job_execution import JobStatus

        mock_jobs = [MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_jobs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_list(mock_session, status=JobStatus.FAILED)

        assert result == mock_jobs

    @pytest.mark.asyncio
    async def test_get_list_with_pagination(self, mock_session):
        """Test pagination with limit and offset."""
        from crud.job_execution import get_list

        mock_jobs = [MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_jobs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_list(mock_session, limit=10, offset=20)

        assert result == mock_jobs

    @pytest.mark.asyncio
    async def test_get_list_empty(self, mock_session):
        """Test returns empty list when no results."""
        from crud.job_execution import get_list

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_list(mock_session)

        assert result == []


class TestGetStats:
    """Tests for get_stats function."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, mock_session):
        """Test stats when no jobs exist."""
        from crud.job_execution import get_stats

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_stats(mock_session)

        assert result["total"] == 0
        assert result["completed"] == 0
        assert result["failed"] == 0
        assert result["running"] == 0
        assert result["scheduled"] == 0
        assert result["avg_duration_ms"] == 0
        assert result["by_type"] == {}

    @pytest.mark.asyncio
    async def test_get_stats_with_jobs(self, mock_session):
        """Test stats calculation with multiple jobs."""
        from crud.job_execution import get_stats
        from models.job_execution import JobStatus

        # Create mock jobs with different statuses
        jobs = [
            MagicMock(
                status=JobStatus.COMPLETED, job_type="reminder", duration_ms=1000
            ),
            MagicMock(
                status=JobStatus.COMPLETED, job_type="reminder", duration_ms=2000
            ),
            MagicMock(status=JobStatus.FAILED, job_type="reminder", duration_ms=500),
            MagicMock(
                status=JobStatus.RUNNING, job_type="memory_extraction", duration_ms=None
            ),
            MagicMock(
                status=JobStatus.SCHEDULED,
                job_type="update_reminders",
                duration_ms=None,
            ),
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = jobs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_stats(mock_session, hours=24)

        assert result["total"] == 5
        assert result["completed"] == 2
        assert result["failed"] == 1
        assert result["running"] == 1
        assert result["scheduled"] == 1
        assert result["avg_duration_ms"] == 1166  # (1000+2000+500) / 3
        assert result["by_type"]["reminder"]["total"] == 3
        assert result["by_type"]["reminder"]["failed"] == 1
        assert result["by_type"]["memory_extraction"]["total"] == 1
        assert result["by_type"]["update_reminders"]["total"] == 1


class TestCleanupOld:
    """Tests for cleanup_old function."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_jobs(self, mock_session):
        """Test that old jobs are deleted."""
        from crud.job_execution import cleanup_old

        old_jobs = [MagicMock(), MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = old_jobs
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await cleanup_old(mock_session, days=7)

        assert result == 3
        assert mock_session.delete.call_count == 3
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_nothing_to_delete(self, mock_session):
        """Test cleanup when no old jobs exist."""
        from crud.job_execution import cleanup_old

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await cleanup_old(mock_session, days=7)

        assert result == 0
        mock_session.delete.assert_not_called()
