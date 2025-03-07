import pytest
from scheduler import parse_cron_expression
from notify_client import send_notification
from rest_client import fetch_scheduled_jobs
import requests
from unittest.mock import patch


def test_parse_cron_expression_valid():
    """Test parsing valid cron expressions"""
    # Test all wildcards
    assert parse_cron_expression("* * * * *") == {
        "minute": "*",
        "hour": "*",
        "day": "*",
        "month": "*",
        "day_of_week": "*"
    }
    
    # Test specific values
    assert parse_cron_expression("0 12 * * 1") == {
        "minute": "0",
        "hour": "12",
        "day": "*",
        "month": "*",
        "day_of_week": "1"
    }
    
    # Test complex expression
    assert parse_cron_expression("*/15 2,12 1-15 * 1-5") == {
        "minute": "*/15",
        "hour": "2,12",
        "day": "1-15",
        "month": "*",
        "day_of_week": "1-5"
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


@patch('requests.post')
def test_send_notification_success(mock_post):
    """Test successful notification sending"""
    # Setup mock
    mock_post.return_value.status_code = 200
    
    # Call function
    send_notification(123, "test message")
    
    # Verify the request was made correctly
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['json'] == {
        "chat_id": 123,
        "message": "test message",
        "priority": "normal"
    }


@patch('requests.post')
def test_send_notification_failure(mock_post):
    """Test notification sending failure"""
    # Setup mock to simulate error
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "Internal Server Error"
    
    # Call function (should not raise exception)
    send_notification(123, "test message")
    
    # Verify the request was made
    mock_post.assert_called_once()


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