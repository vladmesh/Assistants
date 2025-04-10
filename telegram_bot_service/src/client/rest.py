from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp
import structlog
from config.settings import settings

logger = structlog.get_logger()


class RestClient:
    """Async client for REST API."""

    def __init__(self):
        self.base_url = settings.rest_service_url
        self.api_prefix = "/api"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request to API."""
        if not self.session:
            raise RuntimeError(
                "Session is not initialized. Use 'async with' context manager."
            )

        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        logger.debug("Making request", url=url, method=method)

        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error("Request error", url=url, method=method, error=str(e))
            raise

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by telegram_id."""
        try:
            response = await self._make_request(
                "GET", "/users/", params={"telegram_id": telegram_id}
            )

            if not response:
                return None

            if isinstance(response, list):
                return response[0] if response else None

            return response

        except aiohttp.ClientError as e:
            logger.error("Error getting user", telegram_id=telegram_id, error=str(e))
            return None

    async def create_user(
        self, telegram_id: int, username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create new user."""
        return await self._make_request(
            "POST", "/users/", json={"telegram_id": telegram_id, "username": username}
        )

    async def get_or_create_user(
        self, telegram_id: int, username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get or create user."""
        try:
            # Try to find user
            user = await self.get_user(telegram_id)
            if user:
                logger.info("Found existing user", telegram_id=telegram_id)
                return user

            # Create new user if not found
            logger.info("Creating new user", telegram_id=telegram_id)
            return await self.create_user(telegram_id, username)

        except aiohttp.ClientError as e:
            logger.error(
                "Error in get_or_create_user",
                telegram_id=telegram_id,
                error=str(e),
            )
            # Return basic user info in case of error
            return {"id": telegram_id, "telegram_id": telegram_id, "username": username}

    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by user_id."""
        try:
            return await self._make_request("GET", f"/users/{user_id}")
        except aiohttp.ClientError as e:
            logger.error("Error getting user by id", user_id=user_id, error=str(e))
            return None

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get user data by Telegram ID."""
        url = f"{self.base_url}{self.api_prefix}/users/"
        params = {"telegram_id": telegram_id}
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 404:
                    logger.info(
                        "User not found by telegram_id", telegram_id=telegram_id
                    )
                    return None
                response.raise_for_status()  # Raise for other errors
                user_data = await response.json()
                logger.info(
                    "User found by telegram_id",
                    telegram_id=telegram_id,
                    user_id=user_data.get("id"),
                )
                return user_data
        except aiohttp.ClientError as e:
            logger.error(
                "Error getting user by telegram_id",
                telegram_id=telegram_id,
                error=str(e),
            )
            # Optionally re-raise or handle differently
            return None  # Or raise

    async def list_secretaries(self) -> Optional[List[Dict[str, Any]]]:
        """Get a list of available secretary assistants."""
        url = f"{self.base_url}{self.api_prefix}/secretaries/"
        try:
            async with self.session.get(url) as response:
                response.raise_for_status()
                secretaries = await response.json()
                logger.info("Retrieved secretaries list", count=len(secretaries))
                return secretaries
        except aiohttp.ClientError as e:
            logger.error("Error retrieving secretaries list", error=str(e))
            return None

    async def set_user_secretary(
        self, user_id: int, secretary_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Assign a secretary to a user."""
        url = (
            f"{self.base_url}{self.api_prefix}/users/{user_id}/secretary/{secretary_id}"
        )
        try:
            async with self.session.post(url) as response:
                response.raise_for_status()
                link_data = await response.json()
                logger.info(
                    "Successfully set secretary for user",
                    user_id=user_id,
                    secretary_id=secretary_id,
                )
                return link_data
        except aiohttp.ClientError as e:
            logger.error(
                "Error setting secretary for user",
                user_id=user_id,
                secretary_id=secretary_id,
                error=str(e),
            )
            return None

    async def get_user_secretary(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get the currently assigned secretary for a user."""
        url = f"{self.base_url}{self.api_prefix}/users/{user_id}/secretary"
        try:
            async with self.session.get(url) as response:
                if response.status == 404:
                    logger.info("No active secretary found for user", user_id=user_id)
                    return None
                response.raise_for_status()  # Raise for other errors
                secretary_data = await response.json()
                logger.info(
                    "Found active secretary for user",
                    user_id=user_id,
                    secretary_id=secretary_data.get("id"),
                )
                return secretary_data
        except aiohttp.ClientError as e:
            logger.error("Error getting user secretary", user_id=user_id, error=str(e))
            return None

    async def close(self) -> None:
        """Close the aiohttp session."""
