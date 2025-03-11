import pytest
from scheduler import parse_cron_expression
from redis_client import send_notification, OUTPUT_QUEUE
from rest_client import fetch_scheduled_jobs
import requests
from unittest.mock import patch, MagicMock
from pytz import utc


def test_parse_cron_expression_valid():
    """Test parsing valid cron expressions"""
    # Test all wildcards
    assert parse_cron_expression("* * * * *") == {
        "minute": "*",
        "hour": "*",
        "day": "*",
        "month": "*",
        "day_of_week": "*",
        "timezone": utc
    }
    
    # Test specific values
    assert parse_cron_expression("0 12 * * 1") == {
        "minute": "0",
        "hour": "12",
        "day": "*",
        "month": "*",
        "day_of_week": "1",
        "timezone": utc
    }
    
    # Test complex expression
    assert parse_cron_expression("*/15 2,12 1-15 * 1-5") == {
        "minute": "*/15",
        "hour": "2,12",
        "day": "1-15",
        "month": "*",
        "day_of_week": "1-5",
        "timezone": utc
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


@patch('redis_client.redis_client')
def test_send_notification_success(mock_redis):
    """Test successful notification sending"""
    # Setup mock
    mock_redis.rpush.return_value = 1
    
    # Call function
    send_notification(123, "test message")
    
    # Verify the request was made correctly
    mock_redis.rpush.assert_called_once()
    args, kwargs = mock_redis.rpush.call_args
    assert args[0] == OUTPUT_QUEUE
    assert args[1] == '{"chat_id": 123, "response": "test message", "status": "success"}'


@patch('redis_client.redis_client')
def test_send_notification_failure(mock_redis):
    """Test notification sending failure"""
    # Setup mock to simulate error
    mock_redis.rpush.side_effect = Exception("Redis error")
    
    # Call function (should not raise exception)
    send_notification(123, "test message")
    
    # Verify the request was made
    mock_redis.rpush.assert_called_once()


@patch('requests.get')
def test_fetch_scheduled_jobs_success(mock_get):
    """Test successful jobs fetching"""
    # Setup mock
    expected_jobs = [
        {"id": 1, "name": "job1", "cron_expression": "* * * * *"},
        {"id": 2, "name": "job2", "cron_expression": "0 12 * * *"}
    ]
    mock_get.return_value.json.return_value = expected_jobs
    mock_get.return_value.status_code = 200
    
    # Call function
    jobs = fetch_scheduled_jobs()
    
    # Verify results
    assert jobs == expected_jobs
    mock_get.assert_called_once()


@patch('requests.get')
def test_fetch_scheduled_jobs_failure(mock_get):
    """Test jobs fetching failure"""
    # Setup mock to simulate network error
    mock_get.side_effect = requests.RequestException("Network error")
    
    # Call function
    jobs = fetch_scheduled_jobs()
    
    # Verify empty list is returned on error
    assert jobs == []
    mock_get.assert_called_once() 