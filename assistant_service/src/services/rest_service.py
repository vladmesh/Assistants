"""REST service client for interacting with the REST API"""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
from config.settings import settings
from pydantic import BaseModel


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
    tools: List[UUID] = []


class Tool(BaseModel):
    """Tool model from REST service"""

    id: str
    name: str
    description: str
    is_active: bool
    tool_type: str
    input_schema: str  # JSON string
    created_at: str
    updated_at: str
    assistant_id: Optional[str] = None  # ID of sub-assistant for sub_assistant type

    @property
    def input_schema_dict(self) -> Dict[str, Any]:
        """Get input schema as dictionary"""
        return json.loads(self.input_schema)


class UserAssistantThread(BaseModel):
    """User assistant thread model from REST service"""

    id: UUID
    user_id: str
    assistant_id: UUID
    thread_id: str
    last_used: str


class RestServiceClient:
    """Client for interacting with the REST service"""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize the client

        Args:
            base_url: Optional base URL of the REST service. If not provided, uses settings.
        """
        self.base_url = (base_url or settings.REST_SERVICE_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient()
        self._cache: Dict[str, Any] = {}

    async def close(self):
        """Close the HTTP client"""
        await self._client.aclose()

    async def get_assistants(self) -> List[Assistant]:
        """Get list of all assistants

        Returns:
            List of Assistant objects
        """
        response = await self._client.get(f"{self.base_url}/api/assistants/")
        response.raise_for_status()
        return [Assistant(**assistant) for assistant in response.json()]

    async def get_assistant(self, assistant_id: str) -> Assistant:
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

    async def get_assistant_tools(self, assistant_id: str) -> List[Tool]:
        """Get list of tools for an assistant

        Args:
            assistant_id: ID of the assistant

        Returns:
            List of Tool objects
        """
        response = await self._client.get(
            f"{self.base_url}/api/assistants/{assistant_id}/tools"
        )
        response.raise_for_status()
        return [Tool(**tool) for tool in response.json()]

    async def get_tools(self) -> List[Tool]:
        """Get list of all tools

        Returns:
            List of Tool objects
        """
        response = await self._client.get(f"{self.base_url}/api/tools/")
        response.raise_for_status()
        return [Tool(**tool) for tool in response.json()]

    async def get_tool(self, tool_id: str) -> Tool:
        """Get tool by ID

        Args:
            tool_id: ID of the tool to get

        Returns:
            Tool object
        """
        response = await self._client.get(f"{self.base_url}/api/tools/{tool_id}")
        response.raise_for_status()
        return Tool(**response.json())

    async def get_user_secretary(self, user_id: int) -> Assistant:
        """Get secretary assistant for user

        Args:
            user_id: Telegram user ID

        Returns:
            Assistant object

        Raises:
            httpx.HTTPError: If request fails
        """
        response = await self._client.get(
            f"{self.base_url}/api/users/{user_id}/secretary"
        )
        response.raise_for_status()
        return Assistant(**response.json())

    async def get_user_assistant_thread(
        self, user_id: str, assistant_id: UUID
    ) -> Optional[UserAssistantThread]:
        """Get thread for user-assistant pair

        Args:
            user_id: User ID
            assistant_id: Assistant ID

        Returns:
            UserAssistantThread object if found, None otherwise
        """
        try:
            response = await self._client.get(
                f"{self.base_url}/api/users/{user_id}/assistants/{assistant_id}/thread"
            )
            response.raise_for_status()
            return UserAssistantThread(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def create_user_assistant_thread(
        self, user_id: str, assistant_id: UUID, thread_id: str
    ) -> UserAssistantThread:
        """Create or update thread for user-assistant pair

        Args:
            user_id: User ID
            assistant_id: Assistant ID
            thread_id: OpenAI thread ID

        Returns:
            Created/updated UserAssistantThread object
        """
        response = await self._client.post(
            f"{self.base_url}/api/users/{user_id}/assistants/{assistant_id}/thread",
            json={"thread_id": thread_id},
        )
        response.raise_for_status()
        return UserAssistantThread(**response.json())
