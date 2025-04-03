from unittest.mock import patch

import pytest
import requests
from pytz import utc
from redis_client import OUTPUT_QUEUE, send_notification
from rest_client import fetch_scheduled_jobs
from scheduler import execute_job, parse_cron_expression


def test_parse_cron_expression_valid():
    """Test parsing valid cron expressions"""
    # Test all wildcards
    assert parse_cron_expression("* * * * *") == {
        "minute": "*",
        "hour": "*",
        "day": "*",
        "month": "*",
        "day_of_week": "*",
        "timezone": utc,
    }

    # Test specific values
    assert parse_cron_expression("0 12 * * 1") == {
        "minute": "0",
        "hour": "12",
        "day": "*",
        "month": "*",
        "day_of_week": "1",
        "timezone": utc,
    }

    # Test complex expression
    assert parse_cron_expression("*/15 2,12 1-15 * 1-5") == {
        "minute": "*/15",
        "hour": "2,12",
        "day": "1-15",
        "month": "*",
        "day_of_week": "1-5",
        "timezone": utc,
    }


def test_parse_cron_expression_invalid():
    """Test parsing invalid cron expressions"""
    # Test incomplete expression
    with pytest.raises(ValueError):
        parse_cron_expression("* * *")

    # Test empty expression
    with pytest.raises(ValueError):
        parse_cron_expression("")

    # Test invalid format
    with pytest.raises(ValueError):
        parse_cron_expression("* * * * * *")


@patch("redis_client.redis_client")
def test_send_notification_success(mock_redis):
    """Test successful notification sending"""
    # Setup mock
    mock_redis.rpush.return_value = 1

    # Call function
    send_notification(123, "test message", {"priority": "high"})

    # Verify the request was made correctly
    mock_redis.rpush.assert_called_once()
    args, kwargs = mock_redis.rpush.call_args
    assert args[0] == OUTPUT_QUEUE

    # Parse the sent message to verify its structure
    sent_message = args[1]
    assert '"type":"tool_message"' in sent_message
    assert '"user_id":123' in sent_message
    assert '"source":"cron"' in sent_message
    assert '"message":"test message"' in sent_message
    assert '"priority":"high"' in sent_message


@patch("redis_client.redis_client")
def test_send_notification_failure(mock_redis):
    """Test notification sending failure"""
    # Setup mock to simulate error
    mock_redis.rpush.side_effect = Exception("Redis error")

    # Call function and verify it raises the exception
    with pytest.raises(Exception) as exc_info:
        send_notification(123, "test message")

    assert str(exc_info.value) == "Redis error"
    mock_redis.rpush.assert_called_once()


def test_execute_job_success():
    """Test successful job execution"""
    # Setup test data
    test_job = {
        "id": 1,
        "name": "test_job",
        "cron_expression": "* * * * *",
        "user_id": 123,
    }

    # Execute job
    execute_job(test_job)

    # Verify message was sent to Redis
    # Note: We can't verify the exact message content as it's in Redis
    # but we can verify that no exceptions were raised


def test_execute_job_failure():
    """Test job execution failure"""
    # Setup test data with invalid user_id to trigger error
    test_job = {
        "id": 1,
        "name": "test_job",
        "cron_expression": "* * * * *",
        "user_id": None,  # This will cause validation error
    }

    # Execute job and verify it raises the exception
    with pytest.raises(Exception):
        execute_job(test_job)


@patch("requests.get")
def test_fetch_scheduled_jobs_success(mock_get):
    """Test successful jobs fetching"""
    # Setup mock
    expected_jobs = [
        {"id": 1, "name": "job1", "cron_expression": "* * * * *", "user_id": 123},
        {"id": 2, "name": "job2", "cron_expression": "0 12 * * *", "user_id": 456},
    ]
    mock_get.return_value.json.return_value = expected_jobs
    mock_get.return_value.status_code = 200

    # Call function
    jobs = fetch_scheduled_jobs()

    # Verify results
    assert jobs == expected_jobs
    mock_get.assert_called_once()


@patch("requests.get")
def test_fetch_scheduled_jobs_failure(mock_get):
    """Test jobs fetching failure"""
    # Setup mock to simulate network error
    mock_get.side_effect = requests.RequestException("Network error")

    # Call function
    jobs = fetch_scheduled_jobs()

    # Verify empty list is returned on error
    assert jobs == []
    mock_get.assert_called_once()
