"""
REST client for the admin panel using BaseServiceClient.

Provides unified HTTP communication with rest_service.
"""

from typing import Any
from uuid import UUID

from shared_models import BaseServiceClient, ClientConfig, get_logger
from shared_models.api_schemas import (
    AssistantCreate,
    AssistantRead,
    AssistantReadSimple,
    AssistantUpdate,
    GlobalSettingsRead,
    GlobalSettingsUpdate,
    MessageRead,
    TelegramUserRead,
    ToolCreate,
    ToolRead,
    ToolUpdate,
)

from config.settings import settings

logger = get_logger(__name__)


class RestServiceClient(BaseServiceClient):
    """Client for interacting with the REST service."""

    def __init__(self, base_url: str | None = None):
        config = ClientConfig(
            timeout=30.0,
            connect_timeout=5.0,
            max_retries=3,
            retry_min_wait=1.0,
            retry_max_wait=10.0,
            circuit_breaker_fail_max=5,
            circuit_breaker_reset_timeout=60.0,
        )
        super().__init__(
            base_url=(base_url or settings.REST_SERVICE_URL).rstrip("/"),
            service_name="admin_service",
            target_service="rest_service",
            config=config,
        )
        self._cache: dict[str, Any] = {}

    # === Users ===

    async def get_users(self) -> list[TelegramUserRead]:
        """Get list of all users."""
        result = await self.request("GET", "/api/users/")
        if isinstance(result, list):
            return [TelegramUserRead(**user) for user in result]
        return []

    async def get_user_secretary(self, user_id: int) -> AssistantRead | None:
        """Get secretary assistant for user."""
        try:
            result = await self.request("GET", f"/api/users/{user_id}/secretary")
            if result:
                return AssistantRead(**result)
            return None
        except Exception as e:
            if "404" in str(e):
                return None
            raise

    async def set_user_secretary(self, user_id: int, secretary_id: UUID | None) -> None:
        """Set secretary for a user."""
        if secretary_id:
            await self.request("POST", f"/api/users/{user_id}/secretary/{secretary_id}")
        else:
            await self.request("DELETE", f"/api/users/{user_id}/secretary")

    async def get_users_and_secretaries(self):
        """Get list of users and secretary assistants."""
        users = await self.get_users()
        assistants = await self.get_assistants()
        secretary_assistants = [a for a in assistants if a.is_secretary and a.is_active]
        return users, secretary_assistants

    # === Assistants ===

    async def get_assistants(self) -> list[AssistantRead]:
        """Get list of all assistants."""
        result = await self.request("GET", "/api/assistants/")
        if isinstance(result, list):
            return [AssistantRead(**assistant) for assistant in result]
        return []

    async def get_assistant(self, assistant_id: UUID) -> AssistantRead:
        """Get assistant by ID."""
        result = await self.request("GET", f"/api/assistants/{assistant_id}")
        return AssistantRead(**result)

    async def create_assistant(self, assistant: AssistantCreate) -> AssistantReadSimple:
        """Create a new assistant."""
        result = await self.request(
            "POST",
            "/api/assistants/",
            json=assistant.model_dump(exclude_none=True),
        )
        return AssistantReadSimple(**result)

    async def update_assistant(
        self, assistant_id: UUID, assistant: AssistantUpdate
    ) -> AssistantRead:
        """Update an existing assistant."""
        result = await self.request(
            "PUT",
            f"/api/assistants/{assistant_id}",
            json=assistant.model_dump(exclude_none=True),
        )
        return AssistantRead(**result)

    async def delete_assistant(self, assistant_id: UUID) -> None:
        """Delete an assistant."""
        await self.request("DELETE", f"/api/assistants/{assistant_id}")

    # === Tools ===

    async def get_tools(self) -> list[ToolRead]:
        """Get list of all tools."""
        result = await self.request("GET", "/api/tools/")
        if isinstance(result, list):
            return [ToolRead(**tool) for tool in result]
        return []

    async def get_assistant_tools(self, assistant_id: UUID) -> list[ToolRead]:
        """Get list of tools for an assistant."""
        result = await self.request("GET", f"/api/assistants/{assistant_id}/tools")
        if isinstance(result, list):
            return [ToolRead(**tool) for tool in result]
        return []

    async def add_tool_to_assistant(self, assistant_id: UUID, tool_id: UUID) -> None:
        """Add tool to assistant."""
        await self.request("POST", f"/api/assistants/{assistant_id}/tools/{tool_id}")

    async def remove_tool_from_assistant(
        self, assistant_id: UUID, tool_id: UUID
    ) -> None:
        """Remove tool from assistant."""
        await self.request("DELETE", f"/api/assistants/{assistant_id}/tools/{tool_id}")

    async def create_tool(self, tool: ToolCreate) -> ToolRead:
        """Create a new tool."""
        json_payload = tool.model_dump(exclude_none=True)
        result = await self.request("POST", "/api/tools/", json=json_payload)
        return ToolRead(**result)

    async def update_tool(self, tool_id: UUID, tool: ToolUpdate) -> ToolRead:
        """Update an existing tool."""
        result = await self.request(
            "PUT",
            f"/api/tools/{tool_id}",
            json=tool.model_dump(exclude_none=True),
        )
        return ToolRead(**result)

    # === Global Settings ===

    async def get_global_settings(self) -> GlobalSettingsRead:
        """Get the global system settings."""
        result = await self.request("GET", "/api/global-settings/")
        return GlobalSettingsRead(**result)

    async def update_global_settings(
        self, data: GlobalSettingsUpdate
    ) -> GlobalSettingsRead:
        """Update the global system settings."""
        result = await self.request(
            "PUT",
            "/api/global-settings/",
            json=data.model_dump(exclude_unset=True),
        )
        return GlobalSettingsRead(**result)

    # === Messages ===

    async def get_messages(
        self,
        user_id: int,
        assistant_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "desc",
    ) -> list[MessageRead]:
        """Get messages for a user."""
        try:
            params: dict[str, Any] = {
                "user_id": user_id,
                "limit": limit,
                "offset": offset,
                "sort_by": sort_by,
                "sort_order": sort_order,
            }
            if assistant_id:
                params["assistant_id"] = str(assistant_id)

            result = await self.request("GET", "/api/messages/", params=params)
            if isinstance(result, list):
                return [MessageRead(**message) for message in result]
            return []
        except Exception as e:
            logger.error("Error getting messages", error=str(e))
            return []

    # === Monitoring: Job Executions ===

    async def get_job_executions(
        self,
        job_type: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        hours: int = 24,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get job executions with filters."""
        try:
            params: dict[str, Any] = {"hours": hours, "limit": limit, "offset": offset}
            if job_type:
                params["job_type"] = job_type
            if status:
                params["status"] = status
            if user_id:
                params["user_id"] = user_id

            result = await self.request("GET", "/api/job-executions/", params=params)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error("Error getting job executions", error=str(e))
            return []

    async def get_job_stats(self, hours: int = 24) -> dict | None:
        """Get job execution statistics."""
        try:
            result = await self.request(
                "GET", "/api/job-executions/stats", params={"hours": hours}
            )
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error("Error getting job stats", error=str(e))
            return None

    # === Monitoring: Queue Stats ===

    async def get_queue_stats(self) -> list[dict]:
        """Get queue statistics."""
        try:
            result = await self.request("GET", "/api/queue-stats/")
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error("Error getting queue stats", error=str(e))
            return []

    async def get_queue_messages(
        self,
        queue_name: str | None = None,
        user_id: int | None = None,
        correlation_id: str | None = None,
        hours: int = 24,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get queue message logs with filters."""
        try:
            params: dict[str, Any] = {"hours": hours, "limit": limit, "offset": offset}
            if queue_name:
                params["queue_name"] = queue_name
            if user_id:
                params["user_id"] = user_id
            if correlation_id:
                params["correlation_id"] = correlation_id

            result = await self.request(
                "GET", "/api/queue-stats/messages", params=params
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error("Error getting queue messages", error=str(e))
            return []

    # === User Memories ===

    async def get_user_memories(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """Get memories for a user."""
        try:
            result = await self.request(
                "GET",
                f"/api/memories/user/{user_id}",
                params={"limit": limit, "offset": offset},
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error("Error getting user memories", error=str(e))
            return []

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        try:
            await self.request("DELETE", f"/api/memories/{memory_id}")
            return True
        except Exception as e:
            logger.error("Error deleting memory", error=str(e))
            return False
