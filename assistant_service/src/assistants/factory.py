import asyncio  # Add asyncio
from datetime import datetime  # Add datetime
from typing import Dict, Optional, Tuple
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
        # Cache for assistant_uuid -> (instance, config_loaded_at)
        self._assistant_cache: Dict[UUID, Tuple[BaseAssistant, datetime]] = {}
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
            for instance, _ in self._assistant_cache.values():
                if hasattr(instance, "close") and asyncio.iscoroutinefunction(
                    instance.close
                ):
                    try:
                        await instance.close()
                    except Exception as e:
                        logger.warning(
                            f"Error closing assistant instance {getattr(instance, 'assistant_id', 'unknown')}: {e}"
                        )
                elif hasattr(instance, "close"):
                    try:
                        instance.close()  # Assuming synchronous close if not coroutine
                    except Exception as e:
                        logger.warning(
                            f"Error closing assistant instance {getattr(instance, 'assistant_id', 'unknown')} (sync): {e}"
                        )

            # Clear caches after closing instances
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
        secretary_id = None
        assignment_found = False
        async with self._cache_lock:
            assignment = self._secretary_assignments.get(user_id)
            if assignment:
                secretary_id, _ = assignment
                assignment_found = True

        if assignment_found and secretary_id:
            logger.debug(
                f"Found assignment for user {user_id} in cache: secretary_id={secretary_id}"
            )
            try:
                # get_assistant_by_id handles its own caching
                return await self.get_assistant_by_id(
                    secretary_id, user_id=str(user_id)
                )
            except Exception as e:
                logger.exception(
                    f"Failed to get secretary instance {secretary_id} for user {user_id} from cache",
                    error=str(e),
                    exc_info=True,
                )
                # Fall through to default secretary logic on error

        # Fallback: If no assignment found in cache or error getting cached secretary
        log_message = (
            f"No assignment found for user {user_id} in cache, falling back to default secretary."
            if not assignment_found
            else f"Error retrieving cached secretary {secretary_id} for user {user_id}, falling back to default."
        )
        logger.warning(log_message)
        try:
            secretary_data = (
                await self.get_secretary_assistant()
            )  # Fetches default secretary config
            # Get default secretary instance (might be cached by UUID in get_assistant_by_id)
            return await self.get_assistant_by_id(
                secretary_data.id, user_id=str(user_id)
            )
        except Exception as e:
            logger.exception(
                f"Failed to get default secretary for user {user_id}",
                error=str(e),
                exc_info=True,
            )
            raise ValueError(
                f"No secretary assignment found for user {user_id} and failed to get default secretary."
            ) from e

    async def get_assistant_by_id(
        self, assistant_uuid: UUID, user_id: Optional[str] = None
    ) -> BaseAssistant:
        """Get or create assistant instance by its UUID, using cache.

        Args:
            assistant_uuid: The UUID of the assistant.
            user_id: The string ID of the user requesting the assistant (needed for tool init).

        Returns:
            Assistant instance.

        Raises:
            ValueError: If assistant not found or type is unknown.
        """
        # Check cache first (under lock)
        async with self._cache_lock:
            cached_data = self._assistant_cache.get(assistant_uuid)
            if cached_data:
                instance, loaded_at = cached_data
                logger.debug(
                    f"Assistant {assistant_uuid} found in cache (loaded at {loaded_at})."
                )
                # We might add a check here later to see if loaded_at is too old
                # compared to some TTL or a known config change time, but for now,
                # the periodic refresh handles updates based on updated_at from REST.
                return instance

        logger.info(
            f"Assistant {assistant_uuid} not in cache, creating new instance...",
            user_id=user_id,
        )

        try:
            # --- Fetch data (outside lock) ---
            assistant_data = await self.rest_client.get_assistant(str(assistant_uuid))
            if not assistant_data:
                # Should ideally be caught by RestServiceClient, but handle defensively
                raise ValueError(f"Assistant data for UUID {assistant_uuid} not found.")

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

            created_tools = await self.tool_factory.create_langchain_tools(
                tool_definitions=tool_definitions,
                user_id=user_id,
                assistant_id=str(assistant_data.id),
            )

            # Log tool loading results
            if len(created_tools) != len(tool_definitions):
                logger.warning(
                    f"Initialized assistant '{assistant_data.name}' ({assistant_uuid}) with "
                    f"{len(created_tools)} out of {len(tool_definitions)} defined tools due to initialization errors. "
                    f"Check previous logs for details.",
                    extra={"assistant_id": str(assistant_uuid), "user_id": user_id},
                )
            elif not tool_definitions:
                logger.info(
                    f"Assistant '{assistant_data.name}' ({assistant_uuid}) initialized with no tools defined.",
                    extra={"assistant_id": str(assistant_uuid), "user_id": user_id},
                )
            else:
                logger.info(
                    f"Successfully initialized all {len(created_tools)} defined tools for assistant '{assistant_data.name}' ({assistant_uuid}).",
                    extra={"assistant_id": str(assistant_uuid), "user_id": user_id},
                )

            # --- Create assistant instance (outside lock) ---
            if assistant_data.assistant_type == "llm":
                assistant_instance = LangGraphAssistant(
                    assistant_id=str(assistant_data.id),
                    name=assistant_data.name,
                    config=config,
                    tools=created_tools,
                    user_id=user_id,
                    checkpointer=self.checkpointer,
                    **kwargs,
                )
            else:
                # Handle other types or raise error
                logger.error(
                    f"Attempted to create assistant with unknown type: {assistant_data.assistant_type}"
                )
                raise ValueError(
                    f"Unknown assistant type: {assistant_data.assistant_type}"
                )

            # --- Update cache (under lock) ---
            config_loaded_at = getattr(assistant_data, "updated_at", datetime.now())
            async with self._cache_lock:
                # Store the new instance and its load time
                self._assistant_cache[assistant_uuid] = (
                    assistant_instance,
                    config_loaded_at,  # Use updated_at from REST data
                )
                logger.info(
                    f"Created and cached assistant instance {assistant_uuid}",
                    name=assistant_instance.name,
                    loaded_at=config_loaded_at,
                )

            # Return the newly created instance
            return assistant_instance

        except Exception as e:
            logger.exception(
                f"Failed to create assistant instance {assistant_uuid}",
                error=str(e),
                user_id=user_id,
                exc_info=True,
            )
            # Reraise as ValueError to signal failure to the caller
            raise ValueError(
                f"Failed to get or create assistant {assistant_uuid}. Reason: {e}"
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

    async def _preload_assignments(self):
        """Preload secretary assignments and cache assistant instances at startup."""
        logger.info("Preloading secretary assignments...")
        try:
            assignments = (
                await self.rest_client.list_active_user_secretary_assignments()
            )
            logger.info(f"Found {len(assignments)} active assignments.")

            tasks = []
            user_assignments_to_cache = {}
            secretary_ids_to_preload = set()

            for assignment in assignments:
                user_assignments_to_cache[assignment.user_id] = (
                    assignment.secretary_id,
                    assignment.updated_at,
                )
                secretary_ids_to_preload.add(assignment.secretary_id)

            # Preload unique secretaries concurrently
            for secretary_id in secretary_ids_to_preload:
                # Find one user_id associated with this secretary for context during preload
                # This assumes tools might need *some* user context, even if generic
                user_id_for_context = next(
                    (
                        uid
                        for uid, (sid, _) in user_assignments_to_cache.items()
                        if sid == secretary_id
                    ),
                    None,
                )
                if user_id_for_context:
                    tasks.append(
                        self.get_assistant_by_id(
                            secretary_id, user_id=str(user_id_for_context)
                        )
                    )
                else:
                    logger.warning(
                        f"Could not find a user_id for preloading secretary {secretary_id}, skipping preload."
                    )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log preload results
            loaded_count = 0
            failed_count = 0
            for i, result in enumerate(results):
                secretary_id = list(secretary_ids_to_preload)[
                    i
                ]  # Assuming order is preserved
                if isinstance(result, BaseAssistant):
                    loaded_count += 1
                    logger.debug(f"Successfully preloaded assistant {secretary_id}")
                elif isinstance(result, Exception):
                    failed_count += 1
                    logger.error(
                        f"Failed to preload assistant {secretary_id}: {result}",
                        exc_info=isinstance(result, Exception),
                    )

            # Update the assignments cache under lock only after successful preloading attempt
            async with self._cache_lock:
                self._secretary_assignments = user_assignments_to_cache

            logger.info(
                f"Preloading complete. Loaded: {loaded_count}, Failed: {failed_count}, Assignments cached: {len(self._secretary_assignments)}"
            )

        except Exception as e:
            logger.exception(
                "Failed to preload secretary assignments", error=str(e), exc_info=True
            )

    async def _periodic_refresh_cache(self):
        """Periodically refresh secretary assignments and assistant cache."""
        while True:
            try:
                await asyncio.sleep(60)  # Wait 60 seconds before next refresh
                logger.info("Starting periodic cache refresh...")

                # 1. Fetch current assignments from REST
                remote_assignments_list = (
                    await self.rest_client.list_active_user_secretary_assignments()
                )
                remote_assignments_dict: Dict[int, Tuple[UUID, datetime]] = {
                    a.user_id: (a.secretary_id, a.updated_at)
                    for a in remote_assignments_list
                }
                logger.debug(
                    f"Fetched {len(remote_assignments_dict)} remote assignments."
                )

                # 2. Compare with local cache and identify changes (under lock)
                async with self._cache_lock:
                    current_assignments = self._secretary_assignments
                    added_users = (
                        remote_assignments_dict.keys() - current_assignments.keys()
                    )
                    removed_users = (
                        current_assignments.keys() - remote_assignments_dict.keys()
                    )
                    potentially_updated_users = (
                        remote_assignments_dict.keys() & current_assignments.keys()
                    )

                    updated_users = {
                        uid
                        for uid in potentially_updated_users
                        if remote_assignments_dict[uid][1] > current_assignments[uid][1]
                    }

                    # Apply changes to local assignments cache
                    for user_id in removed_users:
                        del self._secretary_assignments[user_id]
                    for user_id in added_users | updated_users:
                        self._secretary_assignments[user_id] = remote_assignments_dict[
                            user_id
                        ]

                    # Identify secretary IDs to check/preload and IDs to potentially remove
                    ids_to_check = {
                        remote_assignments_dict[uid][0]
                        for uid in added_users | updated_users
                    }
                    # We need to update existing assistants if their config changed, even if assignment didn't
                    active_secretary_ids_in_cache = set(self._assistant_cache.keys())
                    current_active_secretary_ids = {
                        assignment[0]
                        for assignment in self._secretary_assignments.values()
                    }
                    ids_to_check.update(
                        active_secretary_ids_in_cache & current_active_secretary_ids
                    )  # Also check active ones already in cache

                logger.info(
                    f"Cache diff: Added={len(added_users)}, Removed={len(removed_users)}, Updated={len(updated_users)}",
                    added=list(added_users),
                    removed=list(removed_users),
                    updated=list(updated_users),
                )

                # 3. Update assistant instances (outside lock)
                tasks = []
                for secretary_id in ids_to_check:
                    tasks.append(self._check_and_update_assistant(secretary_id))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                update_count = sum(1 for r in results if r is True)
                failed_update_count = sum(
                    1 for r in results if isinstance(r, Exception)
                )

                # 4. Clean up assistant cache (under lock)
                async with self._cache_lock:
                    final_active_secretary_ids = {
                        assignment[0]
                        for assignment in self._secretary_assignments.values()
                    }
                    ids_to_remove_from_cache = (
                        self._assistant_cache.keys() - final_active_secretary_ids
                    )
                    for assistant_id in ids_to_remove_from_cache:
                        del self._assistant_cache[assistant_id]
                        logger.info(f"Removed assistant {assistant_id} from cache.")

                logger.info(
                    f"Periodic refresh complete. Updated/Loaded: {update_count}, Failed: {failed_update_count}, Removed from cache: {len(ids_to_remove_from_cache)}"
                )

            except asyncio.CancelledError:
                logger.info("Cache refresh task cancelled.")
                break  # Exit the loop if cancelled
            except Exception as e:
                logger.exception(
                    "Error during periodic cache refresh", error=str(e), exc_info=True
                )
                # Avoid busy-looping on persistent errors
                await asyncio.sleep(300)  # Wait longer after an error

    async def _check_and_update_assistant(self, assistant_id: UUID) -> bool:
        """Check if assistant config changed and update instance in cache if needed."""
        try:
            current_assistant_data = await self.rest_client.get_assistant(
                str(assistant_id)
            )
            if not current_assistant_data:
                logger.warning(
                    f"Assistant {assistant_id} not found during refresh check."
                )
                return False  # Indicate no update occurred

            config_updated_at = current_assistant_data.updated_at

            async with self._cache_lock:
                cached_data = self._assistant_cache.get(assistant_id)

            should_update = False
            if not cached_data:
                should_update = True  # Not in cache, needs loading
                logger.debug(f"Assistant {assistant_id} not in cache. Triggering load.")
            elif (
                config_updated_at
                and cached_data[1]
                and config_updated_at > cached_data[1]
            ):
                should_update = True  # Config is newer
                logger.info(
                    f"Assistant {assistant_id} config updated ({cached_data[1]} -> {config_updated_at}). Triggering reload."
                )
                # Explicitly remove the old entry before reloading to force recreation
                async with self._cache_lock:
                    if assistant_id in self._assistant_cache:
                        del self._assistant_cache[assistant_id]
                        logger.debug(
                            f"Removed stale entry for {assistant_id} from cache before reload."
                        )

            if should_update:
                # Find a relevant user_id for context
                async with self._cache_lock:
                    user_id_for_context = next(
                        (
                            uid
                            for uid, (sid, _) in self._secretary_assignments.items()
                            if sid == assistant_id
                        ),
                        None,
                    )
                if user_id_for_context:
                    logger.debug(
                        f"Reloading assistant {assistant_id} with user context {user_id_for_context}"
                    )
                    # Call get_assistant_by_id - it handles cache update internally
                    await self.get_assistant_by_id(
                        assistant_id, user_id=str(user_id_for_context)
                    )
                    return True  # Indicate update occurred
                else:
                    # This might happen if the assignment was removed between checks
                    logger.warning(
                        f"Could not find user context for reloading assistant {assistant_id}, skipping reload."
                    )
                    return False  # Indicate no update occurred
            else:
                logger.debug(f"Assistant {assistant_id} is up-to-date.")
                return False  # Indicate no update occurred

        except Exception as e:
            logger.error(
                f"Failed to check/update assistant {assistant_id}",
                error=str(e),
                exc_info=True,
            )
            raise  # Reraise exception to be caught by gather in _periodic_refresh_cache
