import asyncio
import base64
import json
from typing import Optional  # Import Optional for type hinting
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata, CheckpointTuple

# Корректный импорт для JsonPlusSerializer
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

# Правильный путь импорта для RestCheckpointSaver
from storage.rest_checkpoint_saver import CheckpointError, RestCheckpointSaver

# --- Fixtures ---


@pytest.fixture
def mock_async_client():
    """Provides a mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    # Mock the response object structure that client methods return
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    # Use MagicMock for the synchronous raise_for_status method
    mock_response.raise_for_status = MagicMock()
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
    return "123"


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
        # Use MagicMock for the synchronous raise_for_status method
        mock_response.raise_for_status = MagicMock()
        mock_async_client.post.return_value = mock_response

        # Call aput
        result_config = await checkpoint_saver.aput(
            test_config, test_checkpoint_data, test_metadata
        )

        # Assertions
        expected_url = f"http://test-rest-service/api/checkpoints/{test_thread_id}"
        # Use json.dumps to ensure metadata serialization matches what aput does
        # Convert CheckpointMetadata to dict for JSON comparison
        expected_metadata_payload = test_metadata  # Already a dict-like object

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
            CheckpointError,
            match=f"Failed to save checkpoint due to request error",
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
        # raise_for_status should be a sync mock raising the error
        mock_http_error = httpx.HTTPStatusError(
            "Server error", request=None, response=mock_response
        )
        mock_response.raise_for_status = MagicMock(side_effect=mock_http_error)
        mock_async_client.post.return_value = mock_response

        with pytest.raises(
            CheckpointError,
            match=f"Failed to save checkpoint due to HTTP error 500",
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
            "checkpoint_metadata": dict(
                test_metadata
            ),  # Convert metadata to plain dict
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        # Use MagicMock for the synchronous raise_for_status method
        mock_response.raise_for_status = MagicMock()
        # Используем MagicMock, чтобы возвращать словарь напрямую, а не корутину
        mock_response.json = MagicMock(return_value=response_json)
        mock_async_client.get.return_value = mock_response

        # Call aget_tuple
        result_tuple: Optional[CheckpointTuple] = await checkpoint_saver.aget_tuple(
            test_config
        )

        # Assertions
        expected_url = f"http://test-rest-service/api/checkpoints/{test_thread_id}"
        mock_async_client.get.assert_called_once_with(expected_url)
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_called_once()

        assert result_tuple is not None
        assert result_tuple.config == test_config
        # Compare checkpoint data after deserialization
        assert result_tuple.checkpoint == test_checkpoint_data
        # Compare metadata
        assert result_tuple.metadata == test_metadata

    async def test_aget_tuple_not_found(
        self, checkpoint_saver, test_config, mock_async_client
    ):
        """Test checkpoint not found (404)."""
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 404
        # raise_for_status should be a sync mock raising the error
        mock_http_error = httpx.HTTPStatusError(
            "Not Found", request=None, response=mock_response
        )
        mock_response.raise_for_status = MagicMock(side_effect=mock_http_error)
        mock_async_client.get.return_value = mock_response

        # Call aget_tuple - should return None on 404
        result_tuple = await checkpoint_saver.aget_tuple(test_config)

        assert result_tuple is None

    async def test_aget_tuple_network_error(
        self, checkpoint_saver, test_config, mock_async_client
    ):
        """Test network error during load."""
        mock_async_client.get.side_effect = httpx.RequestError(
            "Network error", request=None
        )

        with pytest.raises(
            CheckpointError,
            match="Failed to fetch checkpoint due to request error: Network error",
        ):
            await checkpoint_saver.aget_tuple(test_config)

    async def test_aget_tuple_bad_base64(
        self, checkpoint_saver, test_config, test_metadata, mock_async_client
    ):
        """Test handling of bad base64 data from API."""
        response_json = {
            "thread_id": test_config["configurable"]["thread_id"],
            "checkpoint_data_base64": "this is not base64===",
            "checkpoint_metadata": dict(test_metadata),
        }
        mock_response = AsyncMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=response_json)
        mock_async_client.get.return_value = mock_response

        with pytest.raises(
            CheckpointError, match="Failed to decode/deserialize checkpoint"
        ):
            await checkpoint_saver.aget_tuple(test_config)

    async def test_aget_tuple_no_thread_id(self, checkpoint_saver):
        """Test loading with config missing thread_id."""
        bad_config = RunnableConfig(configurable={})
        with pytest.raises(ValueError, match="thread_id missing in config"):
            await checkpoint_saver.aget_tuple(bad_config)
