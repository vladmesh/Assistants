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
