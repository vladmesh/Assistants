from datetime import datetime
from typing import Any, Optional

import httpx
import structlog
from config.settings import Settings

# Import new schemas and validation error
from pydantic import ValidationError

from shared_models.api_schemas import (
    CalendarCredentialsCreate,
    CalendarCredentialsRead,
    TelegramUserRead,
)

logger = structlog.get_logger()


class RestServiceError(Exception):
    """Custom exception for google_calendar_service REST client errors."""

    pass


class RestService:
    def __init__(self, settings: Settings):
        self.base_url = settings.REST_SERVICE_URL
        # Add /api prefix check/ensure
        if not self.base_url.endswith("/api"):
            if self.base_url.endswith("/"):
                self.base_url += "api"
            else:
                self.base_url += "/api"
        self.client = httpx.AsyncClient(timeout=30.0)  # Add timeout

    async def _request(self, method: str, endpoint: str, **kwargs) -> Optional[Any]:
        """Helper method for making requests and handling common errors/responses."""
        url = f"{self.base_url}{endpoint}"  # Assumes endpoint starts with /
        try:
            response = await self.client.request(method, url, **kwargs)
            if response.status_code == 404:
                return None
            response.raise_for_status()  # Raise for other 4xx/5xx errors
            if response.status_code == 204:
                return {}  # Success, no content
            # Handle potential empty response body for non-204 success codes
            if not response.content:
                return {}  # Or perhaps raise an error if content was expected
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error from REST service: {e.response.status_code}",
                url=url,
                method=method,
                response_text=e.response.text[:200],
            )
            raise RestServiceError(
                f"HTTP Error {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error(
                "Request error connecting to REST service",
                url=url,
                method=method,
                error=str(e),
            )
            raise RestServiceError(f"Request failed for {url}: {e}") from e
        except Exception as e:  # Includes JSONDecodeError
            logger.error(
                "Unexpected error during REST request or JSON parsing",
                url=url,
                method=method,
                error=str(e),
                exc_info=True,
            )
            raise RestServiceError(f"Unexpected error for {url}: {e}") from e

    async def get_user(self, user_id: int) -> Optional[TelegramUserRead]:
        """Get user from REST service by user_id. Returns parsed model or None."""
        try:
            response_data = await self._request("GET", f"/users/{user_id}")
            if response_data is None:
                return None  # 404
            return TelegramUserRead(**response_data)
        except ValidationError as e:
            logger.error(
                "Failed to validate get_user response",
                user_id=user_id,
                errors=e.errors(),
                data=response_data,
            )
            raise RestServiceError(
                f"REST API response validation failed for get_user: {e}"
            ) from e
        # Allow RestServiceError from _request to propagate

    async def get_calendar_token(
        self, user_id: int
    ) -> Optional[CalendarCredentialsRead]:
        """Get calendar token for user from REST service. Returns parsed model or None."""
        try:
            # Endpoint seems to be /calendar/user/{user_id}/token based on update method?
            # Let's try the endpoint structure suggested by the PUT request log first.
            # If this fails, it might just be /calendar/{user_id}
            # TODO: Verify the correct GET endpoint in rest_service routes/calendar.py
            response_data = await self._request(
                "GET", f"/calendar/user/{user_id}/token"
            )
            if response_data is None:
                return None  # 404
            return CalendarCredentialsRead(**response_data)
        except ValidationError as e:
            logger.error(
                "Failed to validate get_calendar_token response",
                user_id=user_id,
                errors=e.errors(),
                data=response_data,
            )
            raise RestServiceError(
                f"REST API response validation failed for get_calendar_token: {e}"
            ) from e
        # Allow RestServiceError from _request to propagate

    async def update_calendar_token(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime,
    ) -> bool:
        """Update calendar token for user in REST service via request body."""
        try:
            # Create Pydantic model for the request body
            payload = CalendarCredentialsCreate(
                user_id=user_id,  # Schema might not need user_id if it's in path
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=token_expiry,
            )
            # Send data in JSON body, not params
            response_data = await self._request(
                "PUT",
                f"/calendar/user/{user_id}/token",
                json=payload.model_dump(
                    mode="json"
                ),  # Use Pydantic v2 dump with mode='json'
            )
            # Successful request (200 OK or maybe 204 No Content handled by _request)
            # _request returns None on 404, dict/list on success
            # We just need to know if it succeeded (didn't raise error and wasn't 404)
            return response_data is not None

        except (RestServiceError, ValidationError) as e:
            # Log errors originating from _request or local validation
            logger.error(
                "Failed to update calendar token",
                error=str(e),
                user_id=user_id,
                exc_info=True,
            )
            return False
        except Exception as e:  # Catch any other unexpected error
            logger.error(
                "Unexpected error during update_calendar_token",
                error=str(e),
                user_id=user_id,
                exc_info=True,
            )
            return False

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.info("Google Calendar REST client session closed.")
