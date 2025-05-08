import asyncio  # Add asyncio
from datetime import datetime, timedelta, timezone  # Add timezone and timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import httpx  # Add httpx import
from assistants.base_assistant import BaseAssistant
from assistants.langgraph.langgraph_assistant import LangGraphAssistant

# Project imports
from config.logger import get_logger
from config.settings import Settings

# Import the recommended serializer
from services.rest_service import RestServiceClient

# Import ToolFactory
from tools.factory import ToolFactory

# Импортируем модели Pydantic для глобальных настроек
from shared_models.api_schemas.global_settings import (
    GlobalSettingsBase,
    GlobalSettingsRead,
)
from shared_models.enums import AssistantType

logger = get_logger(__name__)


class AssistantFactory:
    def __init__(self, settings: Settings):
        """Initialize the factory with settings and REST client"""
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

        # --- Атрибуты кэша для глобальных настроек ---
        self._global_settings_cache: Optional[GlobalSettingsRead] = None
        self._global_settings_last_fetched: Optional[datetime] = None
        self._global_settings_cache_ttl = timedelta(
            minutes=5
        )  # Время жизни кэша - 5 минут
        # Дефолтные значения (на случай недоступности API при первом запуске)
        self._default_settings = GlobalSettingsBase(
            summarization_prompt="Default: Summarize the conversation concisely.",
            context_window_size=4096,
        )
        # ---------------------------------------------

        # --- Инициализация логгера ---
        # Убедиться, что logger инициализирован в __init__ или доступен как self.logger
        self.logger = get_logger(__name__)
        # -----------------------------

        # Initialize ToolFactory, passing self (the AssistantFactory instance)
        self.tool_factory = ToolFactory(settings=settings, assistant_factory=self)
        logger.info("AssistantFactory initialized with ToolFactory")

    async def close(self):
        """Close REST client, checkpointer Redis client, and assistant instances"""
        # Close main REST client
        try:
            await self.rest_client.close()
            logger.info("Closed main REST service client.")
        except Exception as e:
            logger.warning(f"Error closing main REST service client: {e}")

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

    async def get_global_settings(self) -> GlobalSettingsBase:
        """
        Публичный метод для получения глобальных настроек.
        Будет использоваться Orchestrator для получения настроек при создании AssistantState.

        Returns:
            GlobalSettingsBase: объект с глобальными настройками
        """
        return await self._get_cached_global_settings()

    async def _get_cached_global_settings(self) -> GlobalSettingsBase:
        """Fetches global settings from REST or cache, returning defaults on failure."""
        now = datetime.now(timezone.utc)
        cache_valid = (
            self._global_settings_cache is not None
            and self._global_settings_last_fetched is not None
            and (now - self._global_settings_last_fetched)
            < self._global_settings_cache_ttl
        )

        if (
            cache_valid and self._global_settings_cache is not None
        ):  # Доп. проверка для mypy
            self.logger.debug("Returning cached global settings.")
            return self._global_settings_cache

        self.logger.info("Fetching global settings from REST service...")
        try:
            # Убедиться, что self.rest_client инициализирован в __init__
            settings = await self.rest_client.get_global_settings()
            if settings:
                self._global_settings_cache = settings
                self._global_settings_last_fetched = now
                self.logger.info(
                    f"Successfully fetched and cached global settings: {settings.model_dump()}"
                )
                return settings
            else:
                # API вернул 200 OK, но тело ответа пустое (None)
                self.logger.warning(
                    "Global settings endpoint returned empty data, using defaults."
                )
                self._global_settings_cache = None  # Сбрасываем кэш
                self._global_settings_last_fetched = (
                    now  # Обновляем время, чтобы не запрашивать сразу
                )
                return self._default_settings

        except httpx.RequestError as e:
            self.logger.error(
                f"HTTP error fetching global settings: {e}. Using defaults or stale cache.",
                exc_info=True,
            )
            if self._global_settings_cache:
                self.logger.warning(
                    "Returning stale cached global settings due to HTTP error."
                )
                return self._global_settings_cache
            self.logger.warning(
                "Returning default global settings due to HTTP error and empty cache."
            )
            return self._default_settings
        except Exception as e:
            self.logger.exception(
                "Unexpected error fetching global settings. Using defaults or stale cache.",
                exc_info=True,
            )
            if self._global_settings_cache:
                self.logger.warning(
                    "Returning stale cached global settings due to unexpected error."
                )
                return self._global_settings_cache
            self.logger.warning(
                "Returning default global settings due to unexpected error and empty cache."
            )
            return self._default_settings

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
        self, assistant_uuid: UUID, user_id: str
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
                # TODO: Add logic here to check if instance config is outdated
                #       based on `loaded_at` and `assistant_data.updated_at`
                #       If outdated, proceed to fetch/create new instance below.
                self.logger.debug(
                    f"Returning cached assistant {assistant_uuid} for user {user_id}"
                )
                return instance

        self.logger.info(
            f"Assistant {assistant_uuid} for user {user_id} not in cache, creating new instance...",
            user_id=user_id,
        )

        try:
            # --- Fetch assistant config data ---
            assistant_data = await self.rest_client.get_assistant(str(assistant_uuid))
            if not assistant_data:
                raise ValueError(
                    f"Assistant config data for UUID {assistant_uuid} not found."
                )

            tool_definitions = await self.rest_client.get_assistant_tools(
                str(assistant_uuid)
            )

            # ---> ПОЛУЧЕНИЕ ГЛОБАЛЬНЫХ НАСТРОЕК <---
            global_settings = await self._get_cached_global_settings()
            # -----------------------------------------

            # --- Prepare config and create tools ---
            assistant_config_dict = getattr(assistant_data, "config", {}) or {}
            config_for_assistant = {
                "model_name": assistant_data.model,
                "temperature": assistant_config_dict.get("temperature", 0.7),
                "api_key": assistant_config_dict.get(
                    "api_key", self.settings.OPENAI_API_KEY
                ),
                "system_prompt": assistant_data.instructions,
                "timeout": assistant_config_dict.get(
                    "timeout", self.settings.HTTP_CLIENT_TIMEOUT
                ),
                "tools": tool_definitions,  # Pass raw tool definitions if needed by base class
                **assistant_config_dict,
            }

            created_tools = await self.tool_factory.create_langchain_tools(
                tool_definitions=tool_definitions,
                user_id=user_id,
                assistant_id=str(assistant_data.id),
            )

            # --- Create Assistant Instance ---
            # Use the actual enum member for comparison
            assistant_type = assistant_data.assistant_type
            assistant_instance: BaseAssistant

            if assistant_type == AssistantType.LLM:
                self.logger.debug(
                    f"Creating LangGraphAssistant instance for {assistant_uuid}, user {user_id}"
                )
                assistant_instance = LangGraphAssistant(
                    assistant_id=str(assistant_uuid),
                    name=assistant_data.name,
                    config=config_for_assistant,  # Pass the prepared dict
                    tools=created_tools,
                    user_id=user_id,
                    rest_client=self.rest_client,
                    # ---> Передаем новые глобальные настройки <---
                    summarization_prompt=global_settings.summarization_prompt,
                    context_window_size=global_settings.context_window_size,
                    # -------------------------------------------
                )
                # Load initial data after creating instance
                self.logger.info(
                    f"Loading initial data for LangGraphAssistant {assistant_uuid} user {user_id}"
                )
                await assistant_instance._load_initial_data()
            else:
                raise ValueError(
                    f"Unknown or unsupported assistant type '{assistant_type}' for assistant {assistant_uuid}"
                )

            # --- Update Cache ---
            if assistant_instance:
                async with self._cache_lock:
                    self._assistant_cache[cache_key] = (
                        assistant_instance,
                        datetime.now(timezone.utc),  # Use timezone.utc
                    )
                self.logger.info(
                    f"Assistant {assistant_uuid} for user {user_id} created and added to cache."
                )
                return assistant_instance
            else:
                raise ValueError("Failed to create assistant instance.")

        except Exception as e:
            logger.exception(
                f"Failed to get or create assistant {assistant_uuid} for user {user_id}",
                error=str(e),
                exc_info=True,  # Include traceback
                assistant_id=str(assistant_uuid),
                user_id=user_id,
            )
            # Re-raise specific error if it was ValueError, otherwise wrap
            if isinstance(e, ValueError):
                raise
            raise ValueError(
                f"Error creating/retrieving assistant {assistant_uuid} for user {user_id}."
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

    # Method adjusted for clarity
    async def _check_and_update_assistant_cache(
        self, cache_key: Tuple[UUID, str], instance: BaseAssistant, loaded_at: datetime
    ):
        """Checks if a cached assistant needs updating and reloads if necessary."""
        assistant_uuid, user_id = cache_key
        try:
            latest_assistant_data = await self.rest_client.get_assistant(
                str(assistant_uuid)
            )
            if latest_assistant_data:
                latest_updated_at = getattr(latest_assistant_data, "updated_at", None)
                if latest_updated_at and loaded_at:
                    # --- Make comparison timezone-aware ---
                    # Ensure both datetimes are aware and compared in UTC
                    if not loaded_at.tzinfo:
                        logger.warning(
                            f"Loaded_at for {cache_key} is naive, assuming UTC."
                        )
                        loaded_at_aware = loaded_at.replace(tzinfo=timezone.utc)
                    else:
                        loaded_at_aware = loaded_at.astimezone(timezone.utc)

                    if not latest_updated_at.tzinfo:
                        logger.warning(
                            f"Latest_updated_at for {cache_key} is naive, assuming UTC."
                        )
                        latest_updated_at_aware = latest_updated_at.replace(
                            tzinfo=timezone.utc
                        )
                    else:
                        latest_updated_at_aware = latest_updated_at.astimezone(
                            timezone.utc
                        )

                    if latest_updated_at_aware > loaded_at_aware:
                        # --- End timezone comparison fix ---
                        logger.info(
                            f"Assistant config for {assistant_uuid} (user {user_id}) has changed. Reloading."
                        )
                        # Remove old instance from cache before reloading
                        async with self._cache_lock:
                            self._assistant_cache.pop(cache_key, None)
                        # Recursively call get_assistant_by_id to reload and cache new instance
                        # This might lead to deep recursion if called rapidly, consider alternative reload mechanism?
                        await self.get_assistant_by_id(assistant_uuid, user_id)
                else:
                    logger.debug(
                        f"Could not compare update times for {cache_key} (missing data)."
                    )
            else:
                logger.warning(
                    f"Could not fetch latest data for assistant {assistant_uuid} during refresh."
                )
        except Exception as e:
            logger.exception(
                f"Error checking/updating cache for assistant {assistant_uuid} (user {user_id}): {e}",
                exc_info=True,
            )

    async def _periodic_refresh(self):
        """Periodically refresh assignments and check for assistant config updates."""
        logger.info("Starting periodic cache refresh cycle...")
        assignments_updated = 0
        assignments_added = 0
        assignments_removed = 0
        assistants_update_failed = 0  # Track failures during fetch for update check

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

        # Check for assistant config updates
        unique_assistant_uuids = set()
        cache_items_to_check = []
        async with self._cache_lock:
            # Create a snapshot of cache items to check to avoid holding lock during awaits
            cache_items_to_check = list(self._assistant_cache.items())
            unique_assistant_uuids = {uuid for (uuid, _), _ in cache_items_to_check}

        if not unique_assistant_uuids:
            logger.info("Periodic refresh cycle complete (no instances to check).")
            return

        logger.debug(
            f"Checking config updates for {len(unique_assistant_uuids)} unique cached assistant UUIDs."
        )
        # Fetch latest config for all unique assistants (can be optimized)
        # This part was potentially causing the error - moved detailed check to helper
        # Instead of fetching all here, we check inside the loop using the helper

        # Iterate through the snapshot of cache items
        for cache_key, (instance, loaded_at) in cache_items_to_check:
            await self._check_and_update_assistant_cache(cache_key, instance, loaded_at)

        logger.info("Periodic refresh cycle complete.")

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
                await asyncio.sleep(600)  # Wait 600 seconds (10 minutes)
            except asyncio.CancelledError:
                logger.info("Periodic refresh loop cancelled.")
                break  # Exit loop cleanly
            except Exception:
                logger.exception("Error in periodic refresh loop", exc_info=True)
                await asyncio.sleep(300)  # Wait longer after error
