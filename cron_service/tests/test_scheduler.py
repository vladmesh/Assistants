import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from dateutil.parser import isoparse
from pytz import utc

from src.scheduler import DateTrigger, _job_func, schedule_job

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_scheduler():
    """Fixture to mock the APScheduler."""
    scheduler = MagicMock()
    scheduler.get_job = MagicMock(return_value=None)  # Default: job doesn't exist
    scheduler.add_job = MagicMock()
    scheduler.remove_job = MagicMock()
    return scheduler


@pytest.fixture
def mock_redis(mocker):
    """Fixture to spy on the Redis client rpush method."""
    # Import the actual client instance from the module
    from src.redis_client import redis_client

    # Spy on the rpush method of the actual instance
    spy = mocker.spy(redis_client, "rpush")
    yield spy  # Yield the spy object itself


@pytest.fixture
def mock_rest_client():
    """Fixture to mock the REST client requests."""
    with patch("src.rest_client.requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def sample_one_time_reminder():
    """Sample one-time reminder data from REST API."""
    # Make trigger_at slightly in the future for testing scheduling
    future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
    return {
        "id": "uuid-one-time-1",
        "user_id": 123,
        "assistant_id": "assistant-abc",
        "created_by_assistant_id": "assistant-creator",
        "type": "one_time",
        "trigger_at": future_time.isoformat(),
        "cron_expression": None,
        "payload": '{"text": "One time reminder", "priority": "normal"}',
        "status": "active",
        "last_triggered_at": None,
        "created_at": datetime(2025, 4, 5, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
        "updated_at": datetime(2025, 4, 5, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_recurring_reminder():
    """Sample recurring reminder data from REST API."""
    return {
        "id": "uuid-recurring-1",
        "user_id": 456,
        "assistant_id": "assistant-def",
        "created_by_assistant_id": "assistant-creator",
        "type": "recurring",
        "trigger_at": None,
        "cron_expression": "0 10 * * *",  # Every day at 10:00
        "payload": '{"check_type": "daily_report", "report_id": "daily_456"}',
        "status": "active",
        "last_triggered_at": None,
        "created_at": datetime(2025, 4, 5, 9, 0, 0, tzinfo=timezone.utc).isoformat(),
        "updated_at": datetime(2025, 4, 5, 9, 0, 0, tzinfo=timezone.utc).isoformat(),
    }


# Patch the global scheduler object within the test
@patch("src.scheduler.scheduler")
def test_schedule_one_time_job(mock_scheduler_global, sample_one_time_reminder):
    """Test scheduling a new one-time job."""
    reminder = sample_one_time_reminder
    job_id = f"reminder_{reminder['id']}"
    # Configure the patched global scheduler mock
    mock_scheduler_global.get_job.return_value = None

    # Pass the actual reminder, schedule_job uses the global scheduler
    schedule_job(reminder)

    mock_scheduler_global.add_job.assert_called_once()
    # Check the call args on the patched global scheduler
    args, kwargs = mock_scheduler_global.add_job.call_args

    assert kwargs["id"] == job_id
    assert kwargs["name"] == f"One-time reminder {reminder['id']}"
    assert isinstance(kwargs["trigger"], DateTrigger)
    # Check trigger time (allowing for minor differences)
    expected_trigger_time = isoparse(reminder["trigger_at"]).astimezone(utc)
    actual_trigger_time = kwargs["trigger"].run_date.astimezone(utc)
    assert abs((actual_trigger_time - expected_trigger_time).total_seconds()) < 1
    assert kwargs["args"] == [reminder]
    # Check the positional argument for the function
    assert args[0] == _job_func


def test_schedule_recurring_job(mock_scheduler, sample_recurring_reminder):
    """Test scheduling a new recurring job."""
    # TODO: Implement test


def test_update_existing_job(mock_scheduler, sample_one_time_reminder):
    """Test updating an existing job (e.g., changing trigger time)."""
    # TODO: Implement test


def test_remove_cancelled_job(mock_scheduler, sample_one_time_reminder):
    """Test removing a job that is cancelled or completed."""
    # TODO: Implement test


def test_job_execution_sends_to_redis(mock_redis, sample_one_time_reminder):
    """Test that executing a job correctly sends a message to Redis."""
    # TODO: Implement test for job execution and Redis message sending


def test_update_jobs_from_rest_flow(
    mock_scheduler,
    mock_rest_client,
    mock_redis,
    sample_one_time_reminder,
    sample_recurring_reminder,
):
    """Test the full flow of fetching from REST and updating scheduler."""
    # TODO: Implement test
