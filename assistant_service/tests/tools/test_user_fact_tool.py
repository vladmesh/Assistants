# assistant_service/tests/tools/test_user_fact_tool.py

import httpx
import pytest
import pytest_asyncio
from config.settings import Settings
from pytest_mock import MockerFixture
from tools.user_fact_tool import UserFactTool
from utils.error_handler import ToolError

from shared_models.api_schemas.user_fact import UserFactCreate

# Constants for testing
TEST_USER_ID = "123"
TEST_ASSISTANT_ID = "assistant_uuid_abc"
TEST_TOOL_ID = "tool_uuid_xyz"
TEST_FACT = "This is a test fact."
TOOL_NAME = "add_user_fact"
TOOL_DESCRIPTION = "Adds a fact about the user."


# Fixtures
@pytest.fixture
def settings() -> Settings:
    """Provides Settings instance with a dummy REST URL."""
    # Minimal settings needed for the tool
    # Note: We rely on the @property REST_SERVICE_URL to be correct
    # If REST_SERVICE_HOST/PORT were needed directly, they'd be set here.
    # Load from .env.test or provide defaults
    return Settings(_env_file=".env.test")  # Ensure it loads test env if needed


@pytest.fixture
def settings_no_url(settings: Settings) -> Settings:
    """Provides Settings instance deliberately missing the URL property logic or host/port."""

    # Create a basic settings object without the necessary host/port
    # or mock the property to return None
    class MockSettings(Settings):
        @property
        def REST_SERVICE_URL(self) -> str | None:
            return None

    return MockSettings(_env_file=".env.test")


@pytest_asyncio.fixture
async def user_fact_tool(settings: Settings) -> UserFactTool:
    """Provides an instance of UserFactTool."""
    tool = UserFactTool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        settings=settings,
        user_id=TEST_USER_ID,
        assistant_id=TEST_ASSISTANT_ID,
        tool_id=TEST_TOOL_ID,
    )
    # Clean up the client after test if it was initialized
    yield tool
    if tool._client:
        await tool._client.aclose()


@pytest_asyncio.fixture
async def user_fact_tool_no_user(settings: Settings) -> UserFactTool:
    """Provides an instance of UserFactTool without a user_id."""
    tool = UserFactTool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        settings=settings,
        user_id=None,  # No user ID
        assistant_id=TEST_ASSISTANT_ID,
        tool_id=TEST_TOOL_ID,
    )
    yield tool
    if tool._client:
        await tool._client.aclose()


@pytest_asyncio.fixture
async def user_fact_tool_invalid_user(settings: Settings) -> UserFactTool:
    """Provides an instance of UserFactTool with an invalid user_id format."""
    tool = UserFactTool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        settings=settings,
        user_id="not-a-number",  # Invalid format
        assistant_id=TEST_ASSISTANT_ID,
        tool_id=TEST_TOOL_ID,
    )
    yield tool
    if tool._client:
        await tool._client.aclose()


@pytest_asyncio.fixture
async def user_fact_tool_no_url(settings_no_url: Settings) -> UserFactTool:
    """Provides an instance of UserFactTool with settings missing the URL."""
    tool = UserFactTool(
        name=TOOL_NAME,
        description=TOOL_DESCRIPTION,
        settings=settings_no_url,  # Settings without URL
        user_id=TEST_USER_ID,
        assistant_id=TEST_ASSISTANT_ID,
        tool_id=TEST_TOOL_ID,
    )
    yield tool
    # Client likely won't initialize, but include cleanup just in case
    if tool._client:
        await tool._client.aclose()


# Tests
@pytest.mark.asyncio
async def test_user_fact_tool_initialization(user_fact_tool: UserFactTool):
    """Test tool initialization."""
    assert user_fact_tool.name == TOOL_NAME
    assert user_fact_tool.description == TOOL_DESCRIPTION
    assert user_fact_tool.user_id == TEST_USER_ID
    assert user_fact_tool.assistant_id == TEST_ASSISTANT_ID
    assert user_fact_tool.tool_id == TEST_TOOL_ID
    assert user_fact_tool.settings is not None
    assert user_fact_tool._client is None  # Client should be lazy loaded


@pytest.mark.asyncio
async def test_execute_success(user_fact_tool: UserFactTool, mocker: MockerFixture):
    """Test successful execution of the tool."""
    # Mock the httpx client instance that get_client would create and return
    mock_async_client = mocker.AsyncMock(
        spec=httpx.AsyncClient
    )  # Keep the mock client instance
    mock_async_client.post.return_value = httpx.Response(
        201, request=httpx.Request("POST", "/")
    )  # Add request

    # Instead of mocking get_client, mock the httpx.AsyncClient class used inside it
    mocker.patch(
        "tools.user_fact_tool.httpx.AsyncClient", return_value=mock_async_client
    )

    result = await user_fact_tool._execute(fact=TEST_FACT)

    assert result == "Факт успешно добавлен."

    # Verify the POST call on the mocked client instance
    expected_url = f"/api/users/{TEST_USER_ID}/facts"
    expected_payload = UserFactCreate(
        user_id=int(TEST_USER_ID), fact=TEST_FACT
    ).model_dump()

    mock_async_client.post.assert_awaited_once_with(expected_url, json=expected_payload)


@pytest.mark.asyncio
async def test_execute_no_user_id(user_fact_tool_no_user: UserFactTool):
    """Test execution without user_id."""
    with pytest.raises(ToolError, match="User ID is required"):
        await user_fact_tool_no_user._execute(fact=TEST_FACT)


@pytest.mark.asyncio
async def test_execute_invalid_user_id_format(
    user_fact_tool_invalid_user: UserFactTool,
):
    """Test execution with invalid user_id format."""
    with pytest.raises(ToolError, match="Invalid User ID format"):
        await user_fact_tool_invalid_user._execute(fact=TEST_FACT)


@pytest.mark.asyncio
async def test_execute_api_error(user_fact_tool: UserFactTool, mocker: MockerFixture):
    """Test execution when the API returns an error."""
    mock_response = httpx.Response(
        404, text="Not Found", request=httpx.Request("POST", "/api/users/123/facts")
    )
    mock_async_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_async_client.post.side_effect = httpx.HTTPStatusError(
        "Not Found", request=mock_response.request, response=mock_response
    )

    # Mock the client class directly
    mocker.patch(
        "tools.user_fact_tool.httpx.AsyncClient", return_value=mock_async_client
    )
    with pytest.raises(
        ToolError, match=r"Ошибка API при добавлении факта \(404\): Not Found"
    ):
        await user_fact_tool._execute(fact=TEST_FACT)
    mock_async_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_network_error(
    user_fact_tool: UserFactTool, mocker: MockerFixture
):
    """Test execution when a network error occurs."""
    mock_async_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_async_client.post.side_effect = httpx.RequestError(
        "Connection failed", request=httpx.Request("POST", "/api/users/123/facts")
    )

    # Mock the client class directly
    mocker.patch(
        "tools.user_fact_tool.httpx.AsyncClient", return_value=mock_async_client
    )
    with pytest.raises(ToolError, match="Сетевая ошибка при добавлении факта:"):
        await user_fact_tool._execute(fact=TEST_FACT)
    mock_async_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_no_settings_url(user_fact_tool_no_url: UserFactTool):
    """Test execution when REST Service URL is not configured."""
    # The error should occur when get_client is called internally by _execute
    with pytest.raises(ToolError, match="REST Service URL not configured"):
        await user_fact_tool_no_url._execute(fact=TEST_FACT)
