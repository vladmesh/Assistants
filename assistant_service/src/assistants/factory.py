import asyncio  # Add asyncio
from datetime import datetime  # Add datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

# Project imports
from config.logger import get_logger
from config.settings import Settings

# Langchain imports
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from services.rest_service import RestServiceClient

# Import ToolFactory
from tools.factory import ToolFactory

from .base_assistant import BaseAssistant
from .langgraph_assistant import LangGraphAssistant

# Import shared model


logger = get_logger(__name__)


class AssistantFactory:
    def __init__(
        self, settings: Settings, checkpointer: Optional[BaseCheckpointSaver] = None
    ):
        """Initialize the factory with settings, REST client, and checkpointer"""
        self.settings = settings
        self.rest_client = RestServiceClient()
        # Cache for user_id -> (secretary_id, assignment_updated_at)
        self._secretary_assignments: Dict[int, Tuple[UUID, datetime]] = {}
        # Cache for (assistant_uuid, user_id) -> (instance, config_loaded_at)
        self._assistant_cache: Dict[
            Tuple[UUID, str], Tuple[BaseAssistant, datetime]
        ] = {}
        # Lock for cache access
        self._cache_lock = asyncio.Lock()

        self.checkpointer = checkpointer or MemorySaver()
        # Initialize ToolFactory, passing self (the AssistantFactory instance)
        self.tool_factory = ToolFactory(settings=self.settings, assistant_factory=self)
        logger.info(
            f"AssistantFactory initialized with checkpointer: {type(self.checkpointer).__name__}"
            f" and ToolFactory"
        )

    async def close(self):
        """Close REST client connection and all assistant instances"""
        await self.rest_client.close()

        # Close all assistant instances from the correct cache
        async with self._cache_lock:  # Ensure thread-safe access during iteration
            # Iterate over a copy of values if modifying the cache during iteration
            # For closing, just iterating is usually fine, but copy is safer if closing fails
            cached_instances = list(self._assistant_cache.values())

        # Close instances outside the lock to prevent blocking cache access for long
        for instance, _ in cached_instances:
            try:
                if hasattr(instance, "close") and asyncio.iscoroutinefunction(
                    instance.close
                ):
                    await instance.close()
                elif hasattr(instance, "close"):
                    instance.close()  # Assuming synchronous close if not coroutine
            except Exception as e:
                logger.warning(
                    f"Error closing assistant instance {getattr(instance, 'assistant_id', 'unknown')}: {e}",
                    user_id=getattr(instance, "user_id", "unknown"),  # Log user_id too
                )

        # Clear caches after closing instances
        async with self._cache_lock:
            self._assistant_cache.clear()
            self._secretary_assignments.clear()  # Clear assignments cache too
        logger.info("AssistantFactory closed REST client and cleared caches.")

    async def get_user_secretary(self, user_id: int) -> BaseAssistant:
        """Get secretary assistant for user using the cached assignments.

        Args:
            user_id: Telegram user ID

        Returns:
            Secretary assistant instance

        Raises:
            ValueError: If no active assignment found and default secretary fails.
        """
        secretary_id_to_fetch: Optional[
            UUID
        ] = None  # Variable to store the ID outside the lock

        async with self._cache_lock:
            assignment = self._secretary_assignments.get(user_id)
            if assignment:
                secretary_id, _ = assignment
                logger.debug(
                    f"Found assignment for user {user_id} in cache: secretary_id={secretary_id}"
                )
                secretary_id_to_fetch = secretary_id  # Store the ID
                # Do NOT call get_assistant_by_id while holding the lock
            else:
                logger.info(
                    f"No assignment found for user {user_id} in cache, attempting direct fetch."
                )

        # If found in cache, fetch assistant instance outside the lock
        if secretary_id_to_fetch:
            try:
                # get_assistant_by_id handles its own caching/locking
                return await self.get_assistant_by_id(
                    secretary_id_to_fetch, user_id=str(user_id)
                )
            except Exception as e:
                logger.exception(
                    f"Failed to get secretary instance {secretary_id_to_fetch} for user {user_id} from cache, falling back to direct fetch.",
                    error=str(e),
                    exc_info=True,
                )
                # Fall through to fetch directly if cache retrieval fails

        # If not found in cache or cache retrieval failed, try fetching directly from REST
        try:
            secretary_data = await self.rest_client.get_user_secretary_assignment(
                user_id
            )
            if secretary_data and secretary_data.get("id"):
                secretary_uuid = UUID(secretary_data["id"])
                logger.info(
                    f"Fetched secretary assignment directly for user {user_id}: secretary_id={secretary_uuid}"
                )
                # Update cache (best effort, lock not strictly needed here as it's informational)
                # We need assignment time for proper cache invalidation later, which isn't in secretary_data
                # self._secretary_assignments[user_id] = (secretary_uuid, datetime.now(UTC))

                # Get the assistant instance (might hit instance cache)
                return await self.get_assistant_by_id(
                    secretary_uuid, user_id=str(user_id)
                )
            else:
                logger.warning(
                    f"No active secretary found for user {user_id} via direct fetch."
                )
                raise ValueError(f"No secretary assigned for user {user_id}")

        except Exception as e:
            logger.exception(
                f"Failed to get secretary assignment for user {user_id} via direct fetch",
                error=str(e),
                exc_info=True,
            )
            # Re-raise specific error if it was ValueError, otherwise wrap
            if isinstance(e, ValueError):
                raise
            raise ValueError(
                f"Error retrieving secretary assignment for user {user_id}."
            ) from e

    async def get_assistant_by_id(
        self, assistant_uuid: UUID, user_id: str  # user_id is now required
    ) -> BaseAssistant:
        """Get or create assistant instance by its UUID and user_id, using cache.

        Args:
            assistant_uuid: The UUID of the assistant.
            user_id: The string ID of the user requesting the assistant (required).

        Returns:
            Assistant instance.

        Raises:
            ValueError: If user_id is not provided, assistant not found, or type is unknown.
        """
        if not user_id:
            raise ValueError(
                "user_id must be provided to get or create an assistant instance."
            )

        cache_key = (assistant_uuid, user_id)
        # Check cache first (under lock)
        async with self._cache_lock:
            cached_data = self._assistant_cache.get(cache_key)
            if cached_data:
                instance, loaded_at = cached_data
                logger.debug(
                    f"Assistant {assistant_uuid} for user {user_id} found in cache (loaded at {loaded_at})."
                )
                # TODO: Add check later to see if config needs refresh based on loaded_at vs assistant_data.updated_at
                return instance

        logger.info(
            f"Assistant {assistant_uuid} for user {user_id} not in cache, creating new instance...",
            user_id=user_id,  # Log user_id correctly
        )

        try:
            # --- Fetch assistant config data (outside lock) ---
            assistant_data = await self.rest_client.get_assistant(str(assistant_uuid))
            if not assistant_data:
                raise ValueError(
                    f"Assistant config data for UUID {assistant_uuid} not found."
                )

            tool_definitions = await self.rest_client.get_assistant_tools(
                str(assistant_uuid)
            )

            # --- Prepare config and create tools (outside lock) ---
            assistant_config_dict = getattr(assistant_data, "config", None) or {}
            config = {
                "api_key": assistant_config_dict.get(
                    "api_key", self.settings.OPENAI_API_KEY
                ),
                "model_name": assistant_data.model,
                "temperature": assistant_config_dict.get("temperature", 0.7),
                "system_prompt": assistant_data.instructions,
                "timeout": assistant_config_dict.get("timeout", 60),
                **assistant_config_dict,
            }
            kwargs = {"is_secretary": assistant_data.is_secretary}

            # Create tools, passing the specific user_id
            created_tools = await self.tool_factory.create_langchain_tools(
                tool_definitions=tool_definitions,
                user_id=user_id,  # Pass the required user_id
                assistant_id=str(assistant_data.id),
            )

            # Log tool loading results
            if len(created_tools) != len(tool_definitions):
                logger.warning(
                    f"Initialized assistant '{assistant_data.name}' ({assistant_uuid}) for user {user_id} with "
                    f"{len(created_tools)} out of {len(tool_definitions)} defined tools due to initialization errors. "
                    f"Check previous logs for details.",
                    extra={"assistant_id": str(assistant_uuid), "user_id": user_id},
                )
            elif not tool_definitions:
                logger.info(
                    f"Assistant '{assistant_data.name}' ({assistant_uuid}) for user {user_id} initialized with no tools defined.",
                    extra={"assistant_id": str(assistant_uuid), "user_id": user_id},
                )
            else:
                logger.info(
                    f"Successfully initialized all {len(created_tools)} defined tools for assistant '{assistant_data.name}' ({assistant_uuid}) for user {user_id}.",
                    extra={"assistant_id": str(assistant_uuid), "user_id": user_id},
                )

            # --- Create assistant instance (outside lock) ---
            if assistant_data.assistant_type == "llm":
                assistant_instance = LangGraphAssistant(
                    assistant_id=str(assistant_data.id),
                    name=assistant_data.name,
                    config=config,
                    tools=created_tools,
                    user_id=user_id,  # Pass user_id to assistant instance
                    checkpointer=self.checkpointer,
                    **kwargs,
                )
            else:
                # Handle other types or raise error
                logger.error(
                    f"Attempted to create assistant with unknown type: {assistant_data.assistant_type}",
                    extra={"assistant_id": str(assistant_uuid), "user_id": user_id},
                )
                raise ValueError(
                    f"Unknown assistant type: {assistant_data.assistant_type}"
                )

            # --- Update cache (under lock) ---
            config_loaded_at = getattr(assistant_data, "updated_at", datetime.now())
            async with self._cache_lock:
                # Store using the (uuid, user_id) key
                self._assistant_cache[cache_key] = (
                    assistant_instance,
                    config_loaded_at,
                )
            logger.info(
                f"Created and cached assistant instance {assistant_uuid} for user {user_id}",
                loaded_at=config_loaded_at,  # Add loaded_at timestamp to log
                name=assistant_data.name,  # Add assistant name to log
                extra={
                    "assistant_id": str(assistant_uuid),
                    "user_id": user_id,
                },  # Keep extra context
            )

            return assistant_instance

        except ValueError as ve:
            logger.error(
                f"ValueError creating assistant {assistant_uuid} for user {user_id}: {ve}",
                exc_info=True,
            )
            raise  # Re-raise ValueError
        except Exception as e:
            logger.exception(
                f"Unexpected error creating assistant {assistant_uuid} for user {user_id}",
                exc_info=True,
            )
            # Wrap other exceptions in ValueError for consistent error handling upstream?
            # Or maybe a custom AssistantCreationError?
            raise ValueError(
                f"Failed to create assistant {assistant_uuid} for user {user_id}."
            ) from e

    async def get_secretary_assistant(self) -> dict:
        """Get secretary assistant config data from REST service.

        Returns:
            Secretary assistant config data (dict-like)

        Raises:
            ValueError: If secretary assistant not found
        """
        assistants = await self.rest_client.get_assistants()
        secretary_data = next((a for a in assistants if a.is_secretary), None)
        if not secretary_data:
            logger.error("Secretary assistant configuration not found in REST service.")
            raise ValueError("Secretary assistant configuration not found")
        logger.info(
            "Found secretary assistant configuration", secretary_id=secretary_data.id
        )
        return secretary_data

    async def create_main_assistant(self) -> BaseAssistant:
        """Creates the main assistant instance (secretary). Primarily for pre-warming or direct access."""
        logger.warning(
            "create_main_assistant called. Consider using get_user_secretary for user-specific instances."
        )
        secretary_data = await self.get_secretary_assistant()
        # We need a user_id here. What should it be? Using a placeholder for now.
        # This method might need rethinking if tools require a real user context.
        logger.warning(
            "Using placeholder user_id 'main_assistant_user' for create_main_assistant"
        )
        placeholder_user_id = "main_assistant_user"
        return await self.get_assistant_by_id(
            secretary_data.id, user_id=placeholder_user_id
        )

    def clear_caches(self):
        self._secretary_cache.clear()
        self._assistant_cache.clear()
        self._secretary_assignments.clear()  # Clear assignments cache too
        logger.info("AssistantFactory caches cleared.")

    async def _preload_secretaries(self):
        """Preload secretary assignments and potentially instances."""
        logger.info("Preloading secretary assignments...")
        assignments_loaded = 0
        assistants_preloaded = 0
        assistants_failed = 0
        assignments_to_preload: List[Tuple[int, UUID]] = []

        try:
            # Use the correct method to list assignments
            remote_assignments = (
                await self.rest_client.list_active_user_secretary_assignments()
            )
            if remote_assignments:
                logger.info(
                    f"Found {len(remote_assignments)} active assignments to preload."
                )
                async with self._cache_lock:
                    for assignment in remote_assignments:
                        # Ensure user_id is int and secretary_id is UUID
                        try:
                            user_id = int(
                                assignment.user_id
                            )  # Already int in UserSecretaryAssignment
                            secretary_id = UUID(
                                str(assignment.secretary_id)
                            )  # Already UUID
                            updated_at = assignment.updated_at  # Already datetime

                            # Store (secretary_id, updated_at) tuple in cache
                            self._secretary_assignments[user_id] = (
                                secretary_id,
                                updated_at,
                            )
                            assignments_to_preload.append((user_id, secretary_id))
                            assignments_loaded += 1
                        except (ValueError, TypeError) as e:
                            logger.warning(
                                f"Skipping invalid assignment data during preload: {assignment}, Error: {e}"
                            )
            else:
                logger.info("No active secretary assignments found to preload.")
                return  # Exit early if no assignments

        except Exception as e:
            logger.exception(
                "Failed to fetch or process secretary assignments during preload",
                error=e,
            )
            return  # Exit if fetching fails

        if not assignments_to_preload:
            logger.info("No valid assignments identified for preloading instances.")
            return  # Exit if no valid assignments were processed

        # Preload assistant instances outside the lock
        # Use asyncio.gather for concurrent preloading
        logger.info(
            f"Attempting to preload {len(assignments_to_preload)} assistant instances..."
        )
        preload_tasks = []
        for user_id, secretary_id in assignments_to_preload:
            # Pass user_id as string to get_assistant_by_id
            preload_tasks.append(
                self.get_assistant_by_id(secretary_id, user_id=str(user_id))
            )

        # Wait for all preload tasks to complete
        results = await asyncio.gather(*preload_tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            user_id, secretary_id = assignments_to_preload[i]
            if isinstance(result, BaseAssistant):
                logger.debug(
                    f"Successfully preloaded assistant {secretary_id} for user {user_id}"
                )
                assistants_preloaded += 1
            else:
                # Log the error from the result if it's an exception
                error_details = (
                    str(result) if isinstance(result, Exception) else "Unknown error"
                )
                logger.error(
                    f"Failed to preload assistant {secretary_id} for user {user_id}",
                    error=error_details,
                    # Optionally include traceback if the result is an exception
                    exc_info=result if isinstance(result, Exception) else None,
                )
                assistants_failed += 1

        logger.info(
            f"Preloading complete. Loaded Instances: {assistants_preloaded}, Failed Instances: {assistants_failed}, Assignments Cached: {assignments_loaded}"
        )

    async def _periodic_refresh(self):
        """Periodically refresh assignments and check assistant config updates."""
        logger.info("Starting periodic cache refresh cycle...")
        assignments_updated = 0
        assignments_added = 0
        assignments_removed = 0
        assistants_configs_checked = 0
        assistants_to_update = 0
        assistants_update_failed = 0  # Track failures during fetch for update check
        assistants_removed_from_cache = 0

        # --- Step 1 & 2: Fetch and Diff Assignments ---
        try:
            # Fetch all currently active assignments
            remote_assignments_list = (
                await self.rest_client.list_active_user_secretary_assignments()
            )
            # Convert list to dict for easier lookup: user_id -> (secretary_id, updated_at)
            remote_assignments_dict = {
                int(a.user_id): (UUID(str(a.secretary_id)), a.updated_at)
                for a in remote_assignments_list
            }
            logger.debug(f"Fetched {len(remote_assignments_dict)} remote assignments.")

        except Exception as e:
            logger.exception(
                "Failed to fetch remote assignments during refresh", error=e
            )
            # Exit the refresh cycle if we can't get assignments
            return

        # --- Step 3: Update Assignment Cache ---
        added_users = []
        removed_users = []
        updated_assignment_users = []

        async with self._cache_lock:
            # Get current assignments from cache
            local_assignments_dict = (
                self._secretary_assignments.copy()
            )  # Work on a copy inside lock? No, modify directly.
            current_users = set(self._secretary_assignments.keys())
            remote_users = set(remote_assignments_dict.keys())

            added_users = list(remote_users - current_users)
            removed_users = list(current_users - remote_users)
            common_users = list(current_users & remote_users)

            # Add new assignments
            for user_id in added_users:
                self._secretary_assignments[user_id] = remote_assignments_dict[user_id]
                assignments_added += 1

            # Remove old assignments
            for user_id in removed_users:
                if user_id in self._secretary_assignments:
                    del self._secretary_assignments[user_id]
                    assignments_removed += 1
                # Note: We don't remove the assistant instance from _assistant_cache here.
                # It might still be needed or will phase out naturally.

            # Check for updated assignments in common users
            for user_id in common_users:
                remote_secretary_id, remote_updated_at = remote_assignments_dict[
                    user_id
                ]
                local_secretary_id, local_updated_at = self._secretary_assignments[
                    user_id
                ]

                # Update if secretary ID changed OR remote timestamp is newer
                if remote_secretary_id != local_secretary_id or (
                    remote_updated_at
                    and local_updated_at
                    and remote_updated_at > local_updated_at
                ):
                    self._secretary_assignments[user_id] = (
                        remote_secretary_id,
                        remote_updated_at,
                    )
                    assignments_updated += 1
                    updated_assignment_users.append(user_id)

        if assignments_added or assignments_removed or assignments_updated:
            logger.info(
                f"Assignment cache updated: Added={assignments_added}, Removed={assignments_removed}, Updated={assignments_updated}",
                # Optionally log user IDs for debugging, can be verbose
                # added_ids=added_users, removed_ids=removed_users, updated_ids=updated_assignment_users
            )
        else:
            logger.debug("No changes detected in secretary assignments.")

        # --- Step 4 & 5: Check for Assistant Config Updates ---
        cached_assistant_keys: List[Tuple[UUID, str]] = []
        async with self._cache_lock:
            # Get a snapshot of current keys under lock
            cached_assistant_keys = list(self._assistant_cache.keys())

        unique_assistant_uuids = list({uuid for uuid, _ in cached_assistant_keys})

        if not unique_assistant_uuids:
            logger.debug("No assistant instances in cache to check for config updates.")
            logger.info("Periodic refresh cycle complete (no instances to check).")
            return  # Nothing more to do

        logger.debug(
            f"Checking config updates for {len(unique_assistant_uuids)} unique cached assistant UUIDs."
        )

        # Fetch current config data for these UUIDs concurrently
        fetch_tasks = {
            uuid: self.rest_client.get_assistant(str(uuid))
            for uuid in unique_assistant_uuids
        }
        results = await asyncio.gather(*fetch_tasks.values(), return_exceptions=True)

        latest_assistant_data_map: Dict[UUID, Any] = {}
        for i, uuid in enumerate(fetch_tasks.keys()):
            result = results[i]
            assistants_configs_checked += 1
            if isinstance(result, Exception):
                logger.warning(
                    f"Failed to fetch latest config for assistant {uuid} during refresh check",
                    error=str(result),
                )
                assistants_update_failed += 1
            elif result:
                # Store the fetched AssistantModel (or whatever the type is)
                latest_assistant_data_map[uuid] = result
            else:
                # Assistant might have been deleted from REST service
                logger.warning(
                    f"Received no data (likely deleted) for assistant {uuid} during refresh check"
                )
                # We will handle removal from cache below if instance exists

        # --- Step 6 & 7: Compare Timestamps and Update Assistant Cache ---
        async with self._cache_lock:
            # Iterate over the snapshot of keys obtained earlier
            for assistant_uuid, user_id in cached_assistant_keys:
                # Double-check if the key still exists in case it was removed concurrently (e.g., by close())
                if (assistant_uuid, user_id) not in self._assistant_cache:
                    logger.debug(
                        f"Assistant instance {assistant_uuid} for user {user_id} was removed concurrently, skipping update check."
                    )
                    continue

                # Get instance and its load time from cache
                instance, loaded_at = self._assistant_cache[(assistant_uuid, user_id)]
                latest_data = latest_assistant_data_map.get(assistant_uuid)

                if latest_data:
                    latest_updated_at = getattr(latest_data, "updated_at", None)
                    if not latest_updated_at:
                        logger.warning(
                            f"Fetched config for assistant {assistant_uuid} is missing 'updated_at' timestamp."
                        )
                        continue  # Cannot compare without timestamp

                    # Compare timestamps (ensure both are valid datetimes)
                    if isinstance(loaded_at, datetime) and isinstance(
                        latest_updated_at, datetime
                    ):
                        if latest_updated_at > loaded_at:
                            logger.info(
                                f"Config for assistant {assistant_uuid} (user: {user_id}) updated remotely ({latest_updated_at} > {loaded_at}). Removing from cache for refresh on next use.",
                                assistant_id=str(assistant_uuid),
                                user_id=user_id,
                            )
                            # Remove from cache. It will be recreated by get_assistant_by_id on next call.
                            del self._assistant_cache[(assistant_uuid, user_id)]
                            assistants_removed_from_cache += 1
                            assistants_to_update += 1  # Mark that an update is needed (will happen on next get)

                            # Optionally close the old instance here? Maybe better to let GC handle it
                            # or rely on the main close() method. For now, just remove from cache.
                        else:
                            # Config is up-to-date or older (older shouldn't happen)
                            logger.debug(
                                f"Assistant {assistant_uuid} (user: {user_id}) config is up-to-date."
                            )
                    else:
                        logger.warning(
                            f"Invalid or missing timestamp for assistant {assistant_uuid} (user: {user_id}). Cannot compare for updates. Loaded: {loaded_at}, Remote: {latest_updated_at}"
                        )

                else:
                    # Latest config data wasn't found (fetch failed or assistant deleted)
                    # Remove the instance from cache as it likely no longer exists or is invalid.
                    logger.warning(
                        f"Config for assistant {assistant_uuid} (user: {user_id}) could not be fetched or assistant deleted. Removing from cache.",
                        assistant_id=str(assistant_uuid),
                        user_id=user_id,
                    )
                    del self._assistant_cache[(assistant_uuid, user_id)]
                    assistants_removed_from_cache += 1
                    # Don't count this as 'to_update', it's a removal due to missing config.

        logger.info(
            f"Assistant config check complete. Checked: {assistants_configs_checked}, Fetch Failures: {assistants_update_failed}, "
            f"Marked for Update (removed from cache): {assistants_removed_from_cache}"
            # Assistants requiring update on next use: {assistants_to_update} - this is same as removed_from_cache now
        )
        logger.info("Periodic refresh cycle finished.")

    # Keep the startup and shutdown logic separate if needed
    async def start_background_tasks(self):
        # Method to start background tasks like periodic refresh
        # This allows calling specific tasks from main.py
        self._refresh_task = asyncio.create_task(self._run_periodic_refresh())

    async def stop_background_tasks(self):
        # Method to stop background tasks
        if hasattr(self, "_refresh_task") and self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.info("Periodic refresh task cancelled successfully.")
            self._refresh_task = None

    async def _run_periodic_refresh(self):
        # Helper coroutine to run the refresh loop
        while True:
            try:
                await self._periodic_refresh()  # Call the actual refresh logic
                await asyncio.sleep(60)  # Wait 60 seconds
            except asyncio.CancelledError:
                logger.info("Periodic refresh loop cancelled.")
                break  # Exit loop cleanly
            except Exception as e:
                logger.exception("Error in periodic refresh loop", exc_info=True)
                await asyncio.sleep(300)  # Wait longer after error
