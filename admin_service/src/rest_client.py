import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from config import settings
from pydantic import BaseModel


class User(BaseModel):
    """User model from REST service"""

    id: int
    telegram_id: int
    username: Optional[str] = None


class Assistant(BaseModel):
    """Assistant model from REST service"""

    id: UUID
    name: str
    is_secretary: bool
    model: str
    instructions: str
    assistant_type: str
    openai_assistant_id: Optional[str] = None
    is_active: bool


class AssistantCreate(BaseModel):
    """Model for creating a new assistant"""

    name: str
    is_secretary: bool = False
    model: str
    instructions: str
    assistant_type: str = "llm"
    openai_assistant_id: Optional[str] = None


class AssistantUpdate(BaseModel):
    """Model for updating an assistant"""

    name: Optional[str] = None
    is_secretary: Optional[bool] = None
    model: Optional[str] = None
    instructions: Optional[str] = None
    assistant_type: Optional[str] = None
    openai_assistant_id: Optional[str] = None
    is_active: Optional[bool] = None


class RestServiceClient:
    """Client for interacting with the REST service"""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize the client

        Args:
            base_url: Optional base URL of the REST service.
                If not provided, uses settings.
        """
        self.base_url = (base_url or settings.REST_SERVICE_URL).rstrip("/")
        self._client = httpx.AsyncClient()
        self._cache: Dict[str, Any] = {}

    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()

    async def get_users(self) -> List[User]:
        """Get list of all users

        Returns:
            List of User objects
        """
        response = await self._client.get(f"{self.base_url}/api/users/all/")
        response.raise_for_status()
        return [User(**user) for user in response.json()]

    async def get_assistants(self) -> List[Assistant]:
        """Get list of all assistants

        Returns:
            List of Assistant objects
        """
        response = await self._client.get(f"{self.base_url}/api/assistants/")
        response.raise_for_status()
        return [Assistant(**assistant) for assistant in response.json()]

    async def get_assistant(self, assistant_id: UUID) -> Assistant:
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
        return Assistant(**response.json())

    async def create_assistant(self, assistant: AssistantCreate) -> Assistant:
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
        return Assistant(**response.json())

    async def update_assistant(
        self, assistant_id: UUID, assistant: AssistantUpdate
    ) -> Assistant:
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
        return Assistant(**response.json())

    async def delete_assistant(self, assistant_id: UUID) -> None:
        """Delete an assistant

        Args:
            assistant_id: ID of the assistant to delete
        """
        response = await self._client.delete(
            f"{self.base_url}/api/assistants/{assistant_id}"
        )
        response.raise_for_status()

    async def set_user_secretary(self, user_id: int, secretary_id: UUID) -> None:
        """Set secretary for a user

        Args:
            user_id: ID of the user
            secretary_id: ID of the secretary assistant
        """
        response = await self._client.post(
            f"{self.base_url}/api/users/{user_id}/secretary/{secretary_id}"
        )
        response.raise_for_status()
