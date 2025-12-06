# rest_service/tests/unit/conftest.py
"""Unit test fixtures - no database, no external services."""

import pytest


@pytest.fixture
def mock_settings():
    """Provide mock settings for unit tests."""
    return {
        "TESTING": True,
        "ASYNC_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    }
