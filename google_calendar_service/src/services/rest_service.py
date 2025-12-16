"""
REST client for google_calendar_service using BaseServiceClient.

Provides unified HTTP communication with rest_service.
"""

from datetime import datetime

from pydantic import ValidationError
from shared_models import BaseServiceClient, ClientConfig, get_logger
from shared_models.api_schemas import (
    CalendarCredentialsCreate,
    CalendarCredentialsRead,
    TelegramUserRead,
)

from config.settings import Settings

logger = get_logger(__name__)


class RestServiceError(Exception):
    """Custom exception for google_calendar_service REST client errors."""


class RestService(BaseServiceClient):
    """REST client for google_calendar_service."""

    def __init__(self, settings: Settings):
        base_url = settings.REST_SERVICE_URL
        # Add /api prefix if not present
        if not base_url.endswith("/api"):
            if base_url.endswith("/"):
                base_url += "api"
            else:
                base_url += "/api"

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
            base_url=base_url,
            service_name="google_calendar_service",
            target_service="rest_service",
            config=config,
        )

    async def get_user(self, user_id: int) -> TelegramUserRead | None:
        """Get user from REST service by user_id."""
        try:
            response_data = await self.request("GET", f"/users/{user_id}")
            if response_data is None:
                return None
            return TelegramUserRead(**response_data)
        except ValidationError as e:
            logger.error(
                "Failed to validate get_user response",
                user_id=user_id,
                errors=e.errors(),
            )
            raise RestServiceError(
                f"REST API response validation failed for get_user: {e}"
            ) from e
        except Exception as e:
            logger.error("Failed to get user", user_id=user_id, error=str(e))
            raise RestServiceError(f"Failed to get user {user_id}: {e}") from e

    async def get_calendar_token(self, user_id: int) -> CalendarCredentialsRead | None:
        """Get calendar token for user from REST service."""
        try:
            response_data = await self.request("GET", f"/calendar/user/{user_id}/token")
            if response_data is None:
                return None
            return CalendarCredentialsRead(**response_data)
        except ValidationError as e:
            logger.error(
                "Failed to validate get_calendar_token response",
                user_id=user_id,
                errors=e.errors(),
            )
            raise RestServiceError(
                f"REST API response validation failed for get_calendar_token: {e}"
            ) from e
        except Exception as e:
            logger.error("Failed to get calendar token", user_id=user_id, error=str(e))
            raise RestServiceError(
                f"Failed to get calendar token for user {user_id}: {e}"
            ) from e

    async def update_calendar_token(
        self,
        user_id: int,
        access_token: str,
        refresh_token: str,
        token_expiry: datetime,
    ) -> bool:
        """Update calendar token for user in REST service."""
        try:
            payload = CalendarCredentialsCreate(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=token_expiry,
            )
            response_data = await self.request(
                "PUT",
                f"/calendar/user/{user_id}/token",
                json=payload.model_dump(mode="json"),
            )
            return response_data is not None
        except (RestServiceError, ValidationError) as e:
            logger.error(
                "Failed to update calendar token",
                error=str(e),
                user_id=user_id,
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error during update_calendar_token",
                error=str(e),
                user_id=user_id,
            )
            return False
