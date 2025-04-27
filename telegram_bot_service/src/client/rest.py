from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp
import structlog
from config.settings import settings

# Import Pydantic validation error and the new schemas
from pydantic import ValidationError

from shared_models.api_schemas import (
    TelegramUserCreate,  # Needed for create_user payload
)
from shared_models.api_schemas import (
    UserSecretaryLinkCreate,  # Needed for set_user_secretary payload
)
from shared_models.api_schemas import (
    AssistantRead,
    TelegramUserRead,
    UserSecretaryLinkRead,
)

logger = structlog.get_logger()


class RestClientError(Exception):
    """Custom exception for REST client errors (e.g., validation, unexpected)."""

    pass


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
    ) -> Optional[Any]:  # Return Optional[Any] as parsing happens in specific methods
        """Make HTTP request to API. Returns raw JSON data or None on 404."""
        if not self.session:
            # Log error and raise specific exception
            logger.error("Session not initialized for REST client")
            raise RestClientError("Session is not initialized.")

        url = f"{self.base_url}{self.api_prefix}{endpoint}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 404:
                    return None  # Return None for 404
                response.raise_for_status()  # Raise exception for other errors (4xx, 5xx)
                # Handle 204 No Content
                if response.status == 204:
                    return {}  # Return empty dict for successful no-content responses
                # Check content type? Assume JSON for now
                return await response.json()
        except aiohttp.ClientResponseError as e:  # Catch HTTP errors explicitly
            logger.error(
                "HTTP error during request",
                url=url,
                method=method,
                status=e.status,
                message=e.message,
                error=str(e),
            )
            # Re-raise as a custom error or specific aiohttp error
            raise RestClientError(
                f"HTTP Error {e.status} for {url}: {e.message}"
            ) from e
        except aiohttp.ClientError as e:  # Catch other client errors (connection, etc.)
            logger.error("Client request error", url=url, method=method, error=str(e))
            raise RestClientError(f"Request failed for {url}: {str(e)}") from e
        except Exception as e:  # Catch potential JSON decode errors, etc.
            logger.error(
                "Unexpected error during request processing",
                url=url,
                method=method,
                error=str(e),
                exc_info=True,
            )
            raise RestClientError(f"Unexpected error for {url}: {str(e)}") from e

    async def get_user(self, telegram_id: int) -> Optional[TelegramUserRead]:
        """Get user by telegram_id. Returns parsed model or None if not found."""
        try:
            response_data = await self._make_request(
                "GET", "/users/by-telegram-id/", params={"telegram_id": telegram_id}
            )

            if response_data is None:
                return None  # User not found (404)

            if not isinstance(response_data, dict):
                logger.error(
                    "Received unexpected data type from get_user_by_telegram_id endpoint",
                    data_type=type(response_data),
                    telegram_id=telegram_id,
                )
                raise RestClientError(
                    "Invalid response format from /users/by-telegram-id/"
                )

            user_data = response_data

            # Parse the dictionary into the Pydantic model
            return TelegramUserRead(**user_data)

        except ValidationError as e:
            logger.error(
                "Failed to validate user data from API",
                telegram_id=telegram_id,
                errors=e.errors(),
                data=user_data,
            )
            raise RestClientError(
                f"API response validation failed for get_user: {e}"
            ) from e
        # Other exceptions (like RestClientError from _make_request) are allowed to propagate

    async def create_user(
        self, telegram_id: int, username: Optional[str] = None
    ) -> TelegramUserRead:
        """Create new user. Returns parsed model."""
        payload = TelegramUserCreate(telegram_id=telegram_id, username=username)
        response_data = await self._make_request(
            "POST", "/users/", json=payload.model_dump()
        )
        if (
            response_data is None
        ):  # Should not happen on successful POST but handle defensively
            logger.error(
                "Create user request returned None unexpectedly",
                telegram_id=telegram_id,
            )
            raise RestClientError("Failed to create user: No response data")
        try:
            # Parse the response into the Read model
            return TelegramUserRead(**response_data)
        except ValidationError as e:
            logger.error(
                "Failed to validate created user data from API",
                telegram_id=telegram_id,
                errors=e.errors(),
                data=response_data,
            )
            raise RestClientError(
                f"API response validation failed for create_user: {e}"
            ) from e

    async def get_or_create_user(
        self, telegram_id: int, username: Optional[str] = None
    ) -> TelegramUserRead:
        """Get or create user. Returns parsed model."""
        # Note: Error handling here needs refinement based on new strategy
        # If get_user raises RestClientError (not None), we should probably stop.
        user = await self.get_user(telegram_id)
        if user:
            logger.info("Found existing user", telegram_id=telegram_id)
            return user

        # If user is None (404), create new user
        logger.info("Creating new user", telegram_id=telegram_id)
        # create_user will raise RestClientError if creation fails
        return await self.create_user(telegram_id, username)

        # Old error handling removed - should be handled by caller now

    async def get_user_by_id(self, user_id: int) -> Optional[TelegramUserRead]:
        """Get user by user_id. Returns parsed model or None if not found."""
        try:
            response_data = await self._make_request("GET", f"/users/{user_id}")
            if response_data is None:
                return None  # 404
            return TelegramUserRead(**response_data)
        except ValidationError as e:
            logger.error(
                "Failed to validate user data from API",
                user_id=user_id,
                errors=e.errors(),
                data=response_data,
            )
            raise RestClientError(
                f"API response validation failed for get_user_by_id: {e}"
            ) from e

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> Optional[TelegramUserRead]:
        """Get user data by Telegram ID. Returns parsed model or None if not found."""
        # This method is redundant with get_user, calling it directly
        return await self.get_user(telegram_id)

    async def list_secretaries(self) -> List[AssistantRead]:
        """Get a list of available secretary assistants. Returns list of parsed models."""
        try:
            response_data = await self._make_request("GET", "/secretaries/")
            if response_data is None:  # Should return [] from API, but handle None
                logger.warning("List secretaries endpoint returned None, expected list")
                return []
            if not isinstance(response_data, list):
                logger.error(
                    "List secretaries endpoint did not return a list",
                    data_type=type(response_data),
                )
                raise RestClientError("Invalid response format for list_secretaries")

            secretaries = [AssistantRead(**item) for item in response_data]
            logger.info("Retrieved secretaries list", count=len(secretaries))
            return secretaries
        except ValidationError as e:
            logger.error(
                "Failed to validate secretaries list data from API",
                errors=e.errors(),
                data=response_data,
            )
            raise RestClientError(
                f"API response validation failed for list_secretaries: {e}"
            ) from e

    async def set_user_secretary(
        self, user_id: int, secretary_id: UUID
    ) -> UserSecretaryLinkRead:
        """Assign a secretary to a user. Returns parsed link model."""
        # Payload for this endpoint might just be IDs in URL, no body needed?
        # Assuming endpoint expects UserSecretaryLinkCreate structure if body is sent
        # Let's assume no body needed, path params are sufficient.
        # If body IS required: payload = UserSecretaryLinkCreate(user_id=user_id, secretary_id=secretary_id)
        # json_payload = payload.model_dump()
        try:
            response_data = await self._make_request(
                "POST",
                f"/users/{user_id}/secretary/{secretary_id}",  # , json=json_payload if needed
            )
            if response_data is None:  # Should not happen on successful POST
                logger.error(
                    "Set user secretary request returned None unexpectedly",
                    user_id=user_id,
                    secretary_id=secretary_id,
                )
                raise RestClientError("Failed to set secretary: No response data")

            link_data = UserSecretaryLinkRead(**response_data)
            logger.info(
                "Successfully set secretary for user",
                user_id=user_id,
                secretary_id=secretary_id,
            )
            return link_data
        except ValidationError as e:
            logger.error(
                "Failed to validate set secretary response data from API",
                user_id=user_id,
                secretary_id=secretary_id,
                errors=e.errors(),
                data=response_data,
            )
            raise RestClientError(
                f"API response validation failed for set_user_secretary: {e}"
            ) from e

    async def get_user_secretary(self, user_id: int) -> Optional[AssistantRead]:
        """Get the currently assigned secretary (Assistant model) for a user."""
        # Endpoint returns the Assistant model directly, not the link
        try:
            response_data = await self._make_request(
                "GET", f"/users/{user_id}/secretary"
            )
            if response_data is None:
                logger.info("No active secretary found for user", user_id=user_id)
                return None  # 404

            secretary_data = AssistantRead(**response_data)
            logger.info(
                "Found active secretary for user",
                user_id=user_id,
                secretary_id=secretary_data.id,
            )
            return secretary_data
        except ValidationError as e:
            logger.error(
                "Failed to validate get secretary response data from API",
                user_id=user_id,
                errors=e.errors(),
                data=response_data,
            )
            raise RestClientError(
                f"API response validation failed for get_user_secretary: {e}"
            ) from e

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            logger.info("REST Client session closed.")
