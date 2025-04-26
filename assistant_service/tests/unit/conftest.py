from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_settings():
    """Mock Settings object."""
    mock = MagicMock()
    mock.redis_url = "redis://mock-redis:6379"
    mock.rest_service_url = "http://mock-rest-service:8000"
    mock.tavily_api_key = "mock_tavily_key"
    # Add other necessary settings attributes here
    return mock


@pytest.fixture
def mock_llm():
    """Mock LangChain ChatOpenAI model."""
    # Use AsyncMock if methods are async
    mock = AsyncMock()
    # Configure mock responses/attributes as needed for tests
    # Example: mock.ainvoke.return_value = AIMessage(content="Mocked response")
    return mock


@pytest.fixture
def mock_openai_client():
    """Mock native OpenAI client."""
    # Use AsyncMock if methods are async
    mock = AsyncMock()
    # Configure mock responses/attributes as needed
    return mock


@pytest.fixture
def mock_rest_client():
    """Mock RestServiceClient."""
    mock = AsyncMock()
    # Configure mock return values for methods like get_user_secretary_config, etc.
    # Example:
    # mock.get_user_secretary_config.return_value = {'assistant_id': 'some_id', ...}
    # mock.create_reminder.return_value = {'id': 'reminder_123', ...}
    # mock.get_tools_by_assistant.return_value = []
    # mock.get_assistant.return_value = MagicMock()
    return mock


# Add other common mocks for unit tests if needed
