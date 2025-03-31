from datetime import datetime
from typing import Optional

import httpx
import structlog
from config.settings import Settings

logger = structlog.get_logger()


class RestService:
    def __init__(self, settings: Settings):
        self.base_url = settings.REST_SERVICE_URL
        self.client = httpx.AsyncClient()

    async def get_user(self, user_id: int) -> Optional[dict]:
        """Get user from REST service by user_id"""
        try:
            response = await self.client.get(f"{self.base_url}/api/users/{user_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to get user", error=str(e), user_id=user_id)
            return None

    async def get_calendar_token(self, user_id: int) -> Optional[dict]:
        """Get calendar token for user from REST service"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/calendar/user/{user_id}/token"
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("Failed to get calendar token", error=str(e), user_id=user_id)
            return None

    async def update_calendar_token(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime,
    ) -> bool:
        """Update calendar token for user in REST service"""
        try:
            response = await self.client.put(
                f"{self.base_url}/api/calendar/user/{user_id}/token",
                params={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expiry": token_expiry.isoformat(),
                },
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(
                "Failed to update calendar token", error=str(e), user_id=user_id
            )
            return False

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
