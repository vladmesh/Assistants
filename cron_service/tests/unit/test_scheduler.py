import logging
from datetime import UTC, datetime, timedelta
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
    future_time = datetime.now(UTC) + timedelta(seconds=10)
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
        "created_at": datetime(2025, 4, 5, 10, 0, 0, tzinfo=UTC).isoformat(),
        "updated_at": datetime(2025, 4, 5, 10, 0, 0, tzinfo=UTC).isoformat(),
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
        "created_at": datetime(2025, 4, 5, 9, 0, 0, tzinfo=UTC).isoformat(),
        "updated_at": datetime(2025, 4, 5, 9, 0, 0, tzinfo=UTC).isoformat(),
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


@patch("src.scheduler.scheduler")
def test_schedule_recurring_job(mock_scheduler_global, sample_recurring_reminder):
    """Test scheduling a new recurring job."""
    from apscheduler.triggers.cron import CronTrigger

    reminder = sample_recurring_reminder
    job_id = f"reminder_{reminder['id']}"
    mock_scheduler_global.get_job.return_value = None

    schedule_job(reminder)

    mock_scheduler_global.add_job.assert_called_once()
    args, kwargs = mock_scheduler_global.add_job.call_args

    assert kwargs["id"] == job_id
    assert kwargs["name"] == f"Recurring reminder {reminder['id']}"
    assert isinstance(kwargs["trigger"], CronTrigger)
    assert args[0] == _job_func


@patch("src.scheduler.scheduler")
def test_update_existing_job(mock_scheduler_global, sample_one_time_reminder):
    """Test updating an existing job (e.g., changing trigger time)."""
    from unittest.mock import MagicMock

    reminder = sample_one_time_reminder
    job_id = f"reminder_{reminder['id']}"

    # Simulate existing job
    existing_job = MagicMock()
    existing_job.id = job_id
    mock_scheduler_global.get_job.return_value = existing_job

    schedule_job(reminder)

    # Should reschedule existing job, not add new
    mock_scheduler_global.reschedule_job.assert_called_once()
    mock_scheduler_global.add_job.assert_not_called()
    call_args = mock_scheduler_global.reschedule_job.call_args
    assert call_args[0][0] == job_id


@patch("src.scheduler.scheduler")
def test_remove_cancelled_job(mock_scheduler_global, sample_one_time_reminder):
    """Test removing a job that is cancelled or completed."""
    from unittest.mock import MagicMock

    reminder = sample_one_time_reminder.copy()
    reminder["status"] = "cancelled"
    job_id = f"reminder_{reminder['id']}"

    # Simulate existing job
    existing_job = MagicMock()
    existing_job.id = job_id
    mock_scheduler_global.get_job.return_value = existing_job

    schedule_job(reminder)

    # Should remove the job
    mock_scheduler_global.remove_job.assert_called_once_with(job_id)
    mock_scheduler_global.add_job.assert_not_called()


@patch("src.scheduler.scheduler")
def test_schedule_job_skips_inactive(mock_scheduler_global, sample_one_time_reminder):
    """Test that inactive reminders are not scheduled."""
    reminder = sample_one_time_reminder.copy()
    reminder["status"] = "paused"

    # No existing job
    mock_scheduler_global.get_job.return_value = None

    schedule_job(reminder)

    # Should not add any job
    mock_scheduler_global.add_job.assert_not_called()


@patch("src.scheduler.send_reminder_trigger")
@patch("src.scheduler.mark_reminder_completed")
def test_job_execution_sends_to_redis(
    mock_mark_completed, mock_send_trigger, sample_one_time_reminder
):
    """Test that executing a job correctly sends a message to Redis."""
    reminder = sample_one_time_reminder

    _job_func(reminder)

    # Verify redis trigger was sent
    mock_send_trigger.assert_called_once_with(reminder)
    # Verify one-time reminder marked as completed
    mock_mark_completed.assert_called_once_with(reminder["id"])


@patch("src.scheduler.send_reminder_trigger")
@patch("src.scheduler.mark_reminder_completed")
def test_job_execution_recurring_not_marked_completed(
    mock_mark_completed, mock_send_trigger, sample_recurring_reminder
):
    """Test that recurring reminders are NOT marked as completed after execution."""
    reminder = sample_recurring_reminder

    _job_func(reminder)

    mock_send_trigger.assert_called_once_with(reminder)
    # Recurring reminders should NOT be marked as completed
    mock_mark_completed.assert_not_called()


@patch("src.scheduler.scheduler")
@patch("src.scheduler.fetch_active_reminders")
def test_update_jobs_from_rest_adds_new_jobs(
    mock_fetch,
    mock_scheduler_global,
    sample_one_time_reminder,
    sample_recurring_reminder,
):
    """Test that update_jobs_from_rest adds new reminder jobs."""
    from src.scheduler import update_jobs_from_rest

    # Return two reminders from REST
    mock_fetch.return_value = [sample_one_time_reminder, sample_recurring_reminder]
    # No existing jobs
    mock_scheduler_global.get_jobs.return_value = []
    mock_scheduler_global.get_job.return_value = None

    update_jobs_from_rest()

    # Should have added both jobs
    assert mock_scheduler_global.add_job.call_count == 2


@patch("src.scheduler.scheduler")
@patch("src.scheduler.fetch_active_reminders")
def test_update_jobs_from_rest_removes_stale_jobs(
    mock_fetch, mock_scheduler_global, sample_one_time_reminder
):
    """Test that update_jobs_from_rest removes jobs no longer in REST."""
    from unittest.mock import MagicMock

    from src.scheduler import update_jobs_from_rest

    # REST returns one reminder
    mock_fetch.return_value = [sample_one_time_reminder]

    # Scheduler has two jobs - one matching, one stale
    existing_job_1 = MagicMock()
    existing_job_1.id = f"reminder_{sample_one_time_reminder['id']}"
    existing_job_2 = MagicMock()
    existing_job_2.id = "reminder_stale-uuid-that-no-longer-exists"

    mock_scheduler_global.get_jobs.return_value = [existing_job_1, existing_job_2]
    mock_scheduler_global.get_job.return_value = (
        existing_job_1  # For the one that exists
    )

    update_jobs_from_rest()

    # Stale job should be removed
    mock_scheduler_global.remove_job.assert_called_with(existing_job_2.id)


@patch("src.scheduler.scheduler")
@patch("src.scheduler.fetch_active_reminders")
def test_update_jobs_from_rest_handles_fetch_failure(mock_fetch, mock_scheduler_global):
    """Test that update_jobs_from_rest handles REST fetch failure gracefully."""
    from src.scheduler import update_jobs_from_rest

    # Simulate fetch failure
    mock_fetch.return_value = None

    # Should not crash, will retry
    update_jobs_from_rest()

    # No jobs should be added or removed on failure
    mock_scheduler_global.add_job.assert_not_called()
