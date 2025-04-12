import asyncio
import base64
import binascii
import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple

# Корректный импорт для JsonPlusSerializer
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# Правильный путь импорта для RestCheckpointSaver
from src.storage.rest_checkpoint_saver import RestCheckpointSaver

# --- Fixtures ---


@pytest.fixture
def mock_async_client():
    """Provides a mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    # Mock the response object structure that client methods return
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.raise_for_status = AsyncMock()  # Mock this method
    # Важно: используем MagicMock вместо AsyncMock для json(), чтобы возвращать
    # словарь напрямую, а не корутину
    mock_response.json = MagicMock(return_value={})  # Default empty json
    client.post = AsyncMock(return_value=mock_response)
    client.get = AsyncMock(return_value=mock_response)
    return client


@pytest.fixture
def test_serializer():
    """Provides a serializer instance (JsonPlusSerializer)."""
    return JsonPlusSerializer()  # Use JsonPlusSerializer


@pytest.fixture
def checkpoint_saver(mock_async_client, test_serializer):
    """Provides an instance of RestCheckpointSaver with mock client and serializer."""
    # Ensure an event loop is available for the constructor
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    return RestCheckpointSaver(
        base_url="http://test-rest-service",
        client=mock_async_client,
        serializer=test_serializer,
    )


@pytest.fixture
def test_thread_id():
    return "thread-123"


@pytest.fixture
def test_config(test_thread_id):
    """Provides a sample RunnableConfig."""
    return RunnableConfig(configurable={"thread_id": test_thread_id})


@pytest.fixture
def test_checkpoint_data():
    """Provides sample checkpoint data."""
    return Checkpoint(
        v=1,
        ts="2024-01-01T00:00:00Z",
        channel_values={"messages": ["hello"]},
        channel_versions={},
        versions_seen={},
    )


@pytest.fixture
def test_metadata():
    """Provides sample checkpoint metadata."""
    return CheckpointMetadata(
        source="input", step=1, writes={"agent": "wrote something"}, task_id="task-xyz"
    )


@pytest.fixture
def serialized_checkpoint(test_serializer, test_checkpoint_data):
    """Provides serialized checkpoint data."""
    # JsonPlusSerializer might return bytes or string, ensure consistency
    data = test_serializer.dumps(test_checkpoint_data)
    return data if isinstance(data, bytes) else data.encode("utf-8")


@pytest.fixture
def base64_checkpoint(serialized_checkpoint):
    """Provides base64 encoded checkpoint data."""
    return base64.b64encode(serialized_checkpoint).decode("utf-8")


# --- Test Class ---


@pytest.mark.asyncio
class TestRestCheckpointSaver:
    # --- aput Tests ---

    async def test_aput_success(
        self,
        checkpoint_saver,
        test_config,
        test_checkpoint_data,
        test_metadata,
        base64_checkpoint,
        mock_async_client,
        test_thread_id,
    ):
        """Test successful checkpoint saving."""
        # Configure mock response for POST
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 201  # Typically 201 Created for POST
        mock_response.raise_for_status = AsyncMock()
        mock_async_client.post.return_value = mock_response

        # Call aput
        result_config = await checkpoint_saver.aput(
            test_config, test_checkpoint_data, test_metadata
        )

        # Assertions
        expected_url = f"http://test-rest-service/api/checkpoints/{test_thread_id}"
        # Use json.dumps to ensure metadata serialization matches what aput does
        # We need to handle potential pydantic_encoder usage within aput
        try:
            # Try serializing directly, assuming simple types in test_metadata
            expected_metadata_payload = json.loads(json.dumps(test_metadata))
        except TypeError:
            # Fallback if direct serialization fails (might happen with complex types)
            # This part might need adjustment based on actual pydantic_encoder behavior
            expected_metadata_payload = {
                "step": test_metadata.get("step", -1)
            }  # Example fallback

        expected_payload = {
            "thread_id": test_thread_id,
            "checkpoint_data_base64": base64_checkpoint,
            "checkpoint_metadata": expected_metadata_payload,
        }

        mock_async_client.post.assert_called_once_with(
            expected_url, json=expected_payload
        )
        mock_response.raise_for_status.assert_called_once()
        assert result_config == test_config

    async def test_aput_network_error(
        self,
        checkpoint_saver,
        test_config,
        test_checkpoint_data,
        test_metadata,
        mock_async_client,
    ):
        """Test network error during save."""
        mock_async_client.post.side_effect = httpx.RequestError(
            "Network error", request=None
        )

        with pytest.raises(
            IOError,
            match=f"Failed to save checkpoint for thread {test_config['configurable']['thread_id']}",
        ):
            await checkpoint_saver.aput(
                test_config, test_checkpoint_data, test_metadata
            )

    async def test_aput_http_error(
        self,
        checkpoint_saver,
        test_config,
        test_checkpoint_data,
        test_metadata,
        mock_async_client,
    ):
        """Test HTTP error during save."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=None, response=mock_response
        )
        mock_async_client.post.return_value = mock_response

        with pytest.raises(
            IOError,
            match=f"Failed to save checkpoint for thread {test_config['configurable']['thread_id']}",
        ):
            await checkpoint_saver.aput(
                test_config, test_checkpoint_data, test_metadata
            )
        mock_response.raise_for_status.assert_called_once()  # Ensure raise_for_status was called

    async def test_aput_no_thread_id(
        self, checkpoint_saver, test_checkpoint_data, test_metadata
    ):
        """Test saving with config missing thread_id."""
        bad_config = RunnableConfig(configurable={})
        with pytest.raises(ValueError, match="thread_id missing in config"):
            await checkpoint_saver.aput(bad_config, test_checkpoint_data, test_metadata)

    # --- aget_tuple Tests ---

    async def test_aget_tuple_success(
        self,
        checkpoint_saver,
        test_config,
        test_checkpoint_data,
        test_metadata,
        base64_checkpoint,
        mock_async_client,
        test_thread_id,
    ):
        """Test successful checkpoint loading."""
        # Prepare the mock response JSON
        response_json = {
            "id": "some-uuid",
            "thread_id": test_thread_id,
            "checkpoint_data_base64": base64_checkpoint,
            "checkpoint_metadata": test_metadata,  # Assuming API returns the dict directly
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = AsyncMock()
        # Используем MagicMock, чтобы возвращать словарь напрямую, а не корутину
        mock_response.json = MagicMock(return_value=response_json)
        mock_async_client.get.return_value = mock_response

        # Call aget_tuple
        result_tuple = await checkpoint_saver.aget_tuple(test_config)

        # Assertions
        expected_url = f"http://test-rest-service/api/checkpoints/{test_thread_id}"
        mock_async_client.get.assert_called_once_with(expected_url)
        mock_response.raise_for_status.assert_called_once()
        assert isinstance(result_tuple, CheckpointTuple)
        assert result_tuple.config == test_config
        # Compare checkpoint dicts for equality
        assert result_tuple.checkpoint == test_checkpoint_data
        assert result_tuple.metadata == test_metadata
        assert result_tuple.parent_config is None  # As per current implementation

    async def test_aget_tuple_not_found(
        self, checkpoint_saver, test_config, mock_async_client
    ):
        """Test loading when checkpoint is not found (404)."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 404
        # raise_for_status should NOT be called on 404 in this specific case in aget_tuple
        mock_response.raise_for_status = AsyncMock()
        mock_async_client.get.return_value = mock_response

        result_tuple = await checkpoint_saver.aget_tuple(test_config)

        assert result_tuple is None
        mock_response.raise_for_status.assert_not_called()  # Important check

    async def test_aget_tuple_network_error(
        self, checkpoint_saver, test_config, mock_async_client
    ):
        """Test network error during load."""
        mock_async_client.get.side_effect = httpx.RequestError(
            "Network error", request=None
        )

        result_tuple = await checkpoint_saver.aget_tuple(test_config)
        assert result_tuple is None

    async def test_aget_tuple_bad_base64(
        self, checkpoint_saver, test_config, test_metadata, mock_async_client
    ):
        """Test loading with invalid base64 data."""
        response_json = {
            "checkpoint_data_base64": "this is not base64",
            "checkpoint_metadata": test_metadata,
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = AsyncMock()
        # Используем MagicMock вместо AsyncMock
        mock_response.json = MagicMock(return_value=response_json)
        mock_async_client.get.return_value = mock_response

        result_tuple = await checkpoint_saver.aget_tuple(test_config)
        assert result_tuple is None

    async def test_aget_tuple_no_thread_id(self, checkpoint_saver):
        """Test loading with config missing thread_id."""
        bad_config = RunnableConfig(configurable={})
        result_tuple = await checkpoint_saver.aget_tuple(bad_config)
        assert result_tuple is None

    async def test_aget_tuple_missing_metadata(
        self, checkpoint_saver, test_config, base64_checkpoint, mock_async_client
    ):
        """Test loading response missing the metadata field."""
        response_json = {
            "checkpoint_data_base64": base64_checkpoint,
            # checkpoint_metadata is missing
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = AsyncMock()
        # Используем MagicMock вместо AsyncMock
        mock_response.json = MagicMock(return_value=response_json)
        mock_async_client.get.return_value = mock_response

        result_tuple = await checkpoint_saver.aget_tuple(test_config)
        assert result_tuple is not None
        assert result_tuple.metadata == {"step": -1}  # Check default value
