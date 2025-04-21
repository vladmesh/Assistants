import asyncio  # Import asyncio for potential use
import base64
import binascii
import json  # Import json module
from datetime import datetime  # Import datetime
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Tuple  # Add List

import httpx
from langchain_core.runnables import RunnableConfig

# Import PendingWrite
# Import BaseCheckpointSaver and related types
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

# Import SerializerProtocol
from langgraph.checkpoint.serde.base import SerializerProtocol
from pydantic.json import pydantic_encoder  # Import pydantic_encoder

# Use the standard LangGraph Pickler
# DEFAULT_SERIALIZER = Pickler()


# Define custom exception for checkpoint errors
class CheckpointError(Exception):
    """Custom exception for checkpoint loading/saving errors."""

    pass


# Inherit from BaseCheckpointSaver instead of AsyncCheckpointSaver
class RestCheckpointSaver(BaseCheckpointSaver):
    """An async-capable checkpoint saver that stores checkpoints via a REST API."""

    client: httpx.AsyncClient  # Use type hint for clarity
    base_url: str
    loop: asyncio.AbstractEventLoop  # Add type hint for loop
    serde: SerializerProtocol  # Rename attribute to serde for consistency

    def __init__(
        self, base_url: str, client: httpx.AsyncClient, serializer: SerializerProtocol
    ):
        super().__init__(serde=serializer)  # Pass serializer as 'serde' to superclass
        self.serde = serializer  # Store the serializer in self.serde

        self.base_url = base_url.rstrip("/")
        self.client = client
        # Add an event loop check/getter if needed for sync context calls
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            # If no running loop, create a new one for sync methods
            # This might be problematic if multiple instances create loops
            # Consider a shared loop or raising an error if not run in async context
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

    # --- Synchronous methods required by BaseCheckpointSaver ---
    # We will implement them by running the async methods synchronously.

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Synchronous wrapper for aget_tuple."""
        # Ensure loop is running if called from a sync context potentially
        if not self.loop.is_running():
            # Use self.serde here if sync methods need serialization (unlikely for get)
            return self.loop.run_until_complete(self.aget_tuple(config))
        else:
            # If loop is already running (e.g., called from within an async func)
            # running run_until_complete might cause issues.
            # This scenario needs careful handling depending on usage context.
            # For simplicity, we might assume it's called from sync context.
            # A more robust solution might involve asyncio.run_coroutine_threadsafe
            # if used across threads.
            # Let's stick to run_until_complete assuming sync context call.
            # Consider logging a warning if loop is already running.
            print(
                "Warning: get_tuple called while event loop is running. Attempting run_until_complete."
            )
            # Use self.serde here if sync methods need serialization (unlikely for get)
            return self.loop.run_until_complete(self.aget_tuple(config))

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """Synchronous wrapper for alist (currently yields nothing)."""
        print("Warning: list() is not implemented and returns an empty iterator.")
        return iter([])  # Correctly return an empty iterator

    def put(self, config: RunnableConfig, checkpoint: Checkpoint) -> RunnableConfig:
        """Synchronous wrapper for aput."""
        if not self.loop.is_running():
            # Use self.serde here if sync methods need serialization
            # Note: The async aput method signature needs update if put needs more args
            return self.loop.run_until_complete(self.aput(config, checkpoint))
        else:
            print(
                "Warning: put called while event loop is running. Attempting run_until_complete."
            )
            # Use self.serde here if sync methods need serialization
            # Note: The async aput method signature needs update if put needs more args
            return self.loop.run_until_complete(self.aput(config, checkpoint))

    # TODO: Implement functional persistence for intermediate writes via REST API.
    # Current implementation is a non-functional placeholder to satisfy the interface.
    def put_writes(
        self,
        config: RunnableConfig,
        writes: List[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Synchronous wrapper for aput_writes. (Minimal implementation)"""
        # For now, this is a no-op as intermediate writes aren't persisted via REST.

    # --- Keep the original async methods ---

    async def setup(self) -> None:
        """Optional: Check connectivity with the REST service."""
        try:
            health_url = f"{self.base_url}/health"
            response = await self.client.get(health_url)
            response.raise_for_status()
            print(f"RestCheckpointSaver: Connection to {self.base_url} successful.")
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(
                f"RestCheckpointSaver: Failed to connect to {self.base_url}. Error: {e}"
            )

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get a checkpoint tuple from the REST service."""
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            print("Error: thread_id missing in config.")
            return None

        url = f"{self.base_url}/api/checkpoints/{thread_id}"
        try:
            response = await self.client.get(url)
            if response.status_code == 404:
                print(f"Checkpoint not found for thread_id: {thread_id}")
                return None
            response.raise_for_status()  # Raise for other 4xx/5xx errors
            data = response.json()
            checkpoint_blob = base64.b64decode(data["checkpoint_data_base64"])
            # Use self.serde for deserialization
            checkpoint = self.serde.loads(checkpoint_blob)
            # Fetch actual metadata from the REST API response
            metadata = data.get("checkpoint_metadata")  # Use .get for safety
            if metadata is None:
                # Handle case where metadata might be missing in older records or if API changes
                # LangGraph Pregel expects a 'step' key. Default to -1 for the initial state before step 0.
                print(
                    f"Warning: checkpoint_metadata missing in response for thread_id {thread_id}. Defaulting to {{'step': -1}}."
                )
                metadata = {"step": -1}
            # Return CheckpointTuple with actual metadata
            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
            )
        except httpx.HTTPStatusError as e:  # Catch HTTP errors first
            # Don't raise for 404, just return None as before
            if e.response.status_code == 404:
                print(f"Checkpoint not found for thread_id: {thread_id}")
                return None
            else:
                # For other HTTP errors, log and raise CheckpointError
                print(f"HTTP error fetching checkpoint for thread_id {thread_id}: {e}")
                raise CheckpointError(
                    f"Failed to fetch checkpoint due to HTTP error {e.response.status_code}"
                ) from e
        except httpx.RequestError as e:  # Catch network/request errors
            print(f"Request error fetching checkpoint for thread_id {thread_id}: {e}")
            # Raise CheckpointError for network issues
            raise CheckpointError(
                f"Failed to fetch checkpoint due to request error: {e}"
            ) from e
        except (
            KeyError,
            TypeError,
            binascii.Error,
            Exception,
        ) as e:  # Catch deserialization/other errors
            # Use logger.exception for better logging with traceback
            # logger.exception(f"Error decoding/deserializing checkpoint for thread_id {thread_id}", exc_info=True)
            print(
                f"Error decoding/deserializing checkpoint for thread_id {thread_id}: {e}"
            )
            # Raise CheckpointError for data issues
            raise CheckpointError(
                f"Failed to decode/deserialize checkpoint: {e}"
            ) from e

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """List checkpoints (not implemented)."""
        print("Warning: alist is not implemented for RestCheckpointSaver")
        if False:  # pragma: no cover
            yield  # pragma: no cover

    # TODO: Implement functional persistence for intermediate writes via REST API.
    # Current implementation is a non-functional placeholder to satisfy the interface.
    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: List[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Save intermediate writes. (Minimal implementation)"""
        # This method is required by BaseCheckpointSaver, but we don't persist
        # intermediate writes via REST in this custom implementation.
        thread_id = config.get("configurable", {}).get("thread_id")

        pass  # Do nothing

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,  # Add metadata
        task_ids: Optional[List[str]] = None,  # Add task_ids
        parent_config: Optional[RunnableConfig] = None,  # Add parent_config
    ) -> RunnableConfig:
        """Save a checkpoint to the REST service."""
        # The implementation only uses config and checkpoint,
        # metadata, task_ids, parent_config are accepted but ignored for now.
        thread_id = config.get("configurable", {}).get("thread_id")
        if not thread_id:
            raise ValueError("thread_id missing in config, cannot save checkpoint.")

        url = f"{self.base_url}/api/checkpoints/{thread_id}"
        try:
            # Use self.serde for serialization
            checkpoint_blob = self.serde.dumps(checkpoint)
            checkpoint_data_base64 = base64.b64encode(checkpoint_blob).decode("utf-8")

            # Use pydantic_encoder to handle datetime and other types within metadata
            # First dump metadata using the encoder, then load it back to get a basic dict
            # This ensures complex objects within metadata are properly serialized if possible by pydantic
            try:
                serializable_metadata_str = json.dumps(
                    metadata, default=pydantic_encoder
                )
                serializable_metadata = json.loads(serializable_metadata_str)
            except TypeError as e:
                # Fallback or logging if pydantic_encoder fails
                print(
                    f"Warning: Could not fully serialize metadata with pydantic_encoder for thread {thread_id}: {e}. Saving potentially incomplete metadata."
                )
                serializable_metadata = {
                    "step": metadata.get("step", -1)
                }  # Save at least the step

            payload = {
                "thread_id": thread_id,
                "checkpoint_data_base64": checkpoint_data_base64,
                "checkpoint_metadata": serializable_metadata,  # Use pydantic-processed metadata
            }
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            print(f"Successfully saved checkpoint for thread_id: {thread_id}")
            return config
        except httpx.HTTPStatusError as e:  # Catch HTTP errors separately
            # Log the specific HTTP error
            print(
                f"HTTP error {e.response.status_code} saving checkpoint for thread_id {thread_id}: {e}"
            )
            # Raise CheckpointError, preserving original exception context
            raise CheckpointError(
                f"Failed to save checkpoint due to HTTP error {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:  # Catch network/request errors
            print(f"Request error saving checkpoint for thread_id {thread_id}: {e}")
            # Raise CheckpointError, preserving original exception context
            raise CheckpointError(
                f"Failed to save checkpoint due to request error: {e}"
            ) from e
        except (
            TypeError,
            binascii.Error,
            Exception,
        ) as e:  # Catch serialization or other errors
            # Log the specific error (e.g., serialization failure)
            # logger.exception(f"Error serializing or saving checkpoint for thread_id {thread_id}", exc_info=True)
            print(
                f"Error serializing or saving checkpoint for thread_id {thread_id}: {e}"
            )
            # Raise CheckpointError, preserving original exception context
            raise CheckpointError(f"Failed to serialize or save checkpoint: {e}") from e
