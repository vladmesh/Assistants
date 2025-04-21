"""REST client for the admin panel"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from config.settings import settings

from shared_models.api_schemas import (
    AssistantCreate,
    AssistantRead,
    AssistantReadSimple,
    AssistantUpdate,
    TelegramUserRead,
    ToolCreate,
    ToolRead,
    ToolUpdate,
)

logger = logging.getLogger(__name__)


class RestServiceClient:
    """Client for interacting with the REST service."""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize the client.

        Args:
            base_url: Optional base URL for the REST service.
                     If not provided, uses settings.REST_SERVICE_URL
        """
        self.base_url = (base_url or settings.REST_SERVICE_URL).rstrip("/")
        self._client = httpx.AsyncClient()
        self._cache: Dict[str, Any] = {}

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_users(self) -> List[TelegramUserRead]:
        """Get list of all users."""
        response = await self._client.get(f"{self.base_url}/api/users/")
        response.raise_for_status()
        return [TelegramUserRead(**user) for user in response.json()]

    async def get_assistants(self) -> List[AssistantRead]:
        """Get list of all assistants."""
        response = await self._client.get(f"{self.base_url}/api/assistants/")
        response.raise_for_status()
        return [AssistantRead(**assistant) for assistant in response.json()]

    async def get_assistant(self, assistant_id: UUID) -> AssistantRead:
        """Get assistant by ID

        Args:
            assistant_id: ID of the assistant to get

        Returns:
            Assistant object
        """
        response = await self._client.get(
            f"{self.base_url}/api/assistants/{assistant_id}"
        )
        response.raise_for_status()
        return AssistantRead(**response.json())

    async def create_assistant(self, assistant: AssistantCreate) -> AssistantReadSimple:
        """Create a new assistant

        Args:
            assistant: Assistant data to create

        Returns:
            Created Assistant object
        """
        response = await self._client.post(
            f"{self.base_url}/api/assistants/",
            json=assistant.model_dump(exclude_none=True),
        )
        response.raise_for_status()
        return AssistantReadSimple(**response.json())

    async def update_assistant(
        self, assistant_id: UUID, assistant: AssistantUpdate
    ) -> AssistantRead:
        """Update an existing assistant

        Args:
            assistant_id: ID of the assistant to update
            assistant: Updated assistant data

        Returns:
            Updated Assistant object
        """
        response = await self._client.put(
            f"{self.base_url}/api/assistants/{assistant_id}",
            json=assistant.model_dump(exclude_none=True),
        )
        response.raise_for_status()
        return AssistantRead(**response.json())

    async def delete_assistant(self, assistant_id: UUID) -> None:
        """Delete an assistant

        Args:
            assistant_id: ID of the assistant to delete
        """
        response = await self._client.delete(
            f"{self.base_url}/api/assistants/{assistant_id}"
        )
        response.raise_for_status()

    async def set_user_secretary(
        self, user_id: int, secretary_id: Optional[UUID]
    ) -> None:
        """Set secretary for a user.

        Args:
            user_id: User ID
            secretary_id: Secretary assistant ID or None to remove secretary
        """
        if secretary_id:
            response = await self._client.post(
                f"{self.base_url}/api/users/{user_id}/secretary/{secretary_id}",
            )
        else:
            # Если secretary_id is None, удаляем связь
            response = await self._client.delete(
                f"{self.base_url}/api/users/{user_id}/secretary",
            )
        response.raise_for_status()

    async def get_users_and_secretaries(self):
        """Get list of users and secretary assistants."""
        users = await self.get_users()
        assistants = await self.get_assistants()
        secretary_assistants = [a for a in assistants if a.is_secretary and a.is_active]
        return users, secretary_assistants

    async def get_user_secretary(self, user_id: int) -> Optional[AssistantRead]:
        """Get secretary assistant for user.

        Args:
            user_id: User ID

        Returns:
            Assistant object if found, None otherwise
        """
        try:
            response = await self._client.get(
                f"{self.base_url}/api/users/{user_id}/secretary"
            )
            # Check for 404 first via exception handling below
            response.raise_for_status()
            # Explicitly check if response body is valid JSON data
            json_data = response.json()
            if json_data:
                return AssistantRead(**json_data)
            else:
                # Handle cases where response is 200 OK but body is null or empty
                logger.warning(
                    f"Received success status but null/empty body for user {user_id} secretary."
                )
                return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def get_tools(self) -> List[ToolRead]:
        """Get list of all tools."""
        response = await self._client.get(f"{self.base_url}/api/tools/")
        response.raise_for_status()
        return [ToolRead(**tool) for tool in response.json()]

    async def get_assistant_tools(self, assistant_id: UUID) -> List[ToolRead]:
        """Get list of tools for an assistant."""
        response = await self._client.get(
            f"{self.base_url}/api/assistants/{assistant_id}/tools"
        )
        response.raise_for_status()
        return [ToolRead(**tool) for tool in response.json()]

    async def add_tool_to_assistant(self, assistant_id: UUID, tool_id: UUID) -> None:
        """Add tool to assistant."""
        response = await self._client.post(
            f"{self.base_url}/api/assistants/{assistant_id}/tools/{tool_id}"
        )
        response.raise_for_status()

    async def remove_tool_from_assistant(
        self, assistant_id: UUID, tool_id: UUID
    ) -> None:
        """Remove tool from assistant."""
        response = await self._client.delete(
            f"{self.base_url}/api/assistants/{assistant_id}/tools/{tool_id}"
        )
        response.raise_for_status()

    async def create_tool(self, tool: ToolCreate) -> ToolRead:
        """Create a new tool

        Args:
            tool: Tool data to create

        Returns:
            Created Tool object
        """
        response = await self._client.post(
            f"{self.base_url}/api/tools/",
            json=tool.model_dump(exclude_none=True),
        )
        response.raise_for_status()
        return ToolRead(**response.json())

    async def update_tool(self, tool_id: UUID, tool: ToolUpdate) -> ToolRead:
        """Update an existing tool

        Args:
            tool_id: ID of the tool to update
            tool: Updated tool data

        Returns:
            Updated Tool object
        """
        response = await self._client.put(
            f"{self.base_url}/api/tools/{tool_id}",
            json=tool.model_dump(exclude_none=True),
        )
        response.raise_for_status()
        return ToolRead(**response.json())
