"""Test datetime utilities for timezone awareness."""

from datetime import UTC, datetime


def get_utc_now() -> datetime:
    """Return aware UTC timestamp - matches models.base.get_utc_now implementation."""
    return datetime.now(UTC)


def test_get_utc_now_returns_aware():
    """Test that get_utc_now returns timezone-aware datetime."""
    dt = get_utc_now()
    assert dt.tzinfo is UTC
    assert dt.tzinfo is not None


def test_utc_now_is_recent():
    """Test that get_utc_now returns a recent timestamp."""
    before = datetime.now(UTC)
    dt = get_utc_now()
    after = datetime.now(UTC)
    assert before <= dt <= after
