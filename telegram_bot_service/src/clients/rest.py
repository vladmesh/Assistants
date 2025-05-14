from typing import Any, List, Optional
from uuid import UUID

import aiohttp
import structlog
from config.settings import settings
from pydantic import ValidationError

# Group imports from shared_models
from shared_models.api_schemas import (
    AssistantRead,
    TelegramUserCreate,
    TelegramUserRead,
    UserSecretaryLinkRead,
    MessageCreate,
    MessageRead,
)

logger = structlog.get_logger()


class RestClientError(Exception):
    """Custom exception for REST client errors (e.g., validation, unexpected)."""


class RestClient:
    """Async client for REST API."""

    def __init__(self):
        self.base_url = settings.rest_service_url
        self.api_prefix = "/api"
        self.session: Optional[aiohttp.ClientSession] = None

    # Restore context manager methods
    async def __aenter__(self):
        # Initialize session when entering context
        # Ensure session is not already created if client is reused
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.debug("RestClient: aiohttp session created in __aenter__.")
        else:
            logger.warning("RestClient: __aenter__ called with existing open session.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Close session when exiting context
        await self.close()

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Any]:
        """Make HTTP request to API. Returns raw JSON data or None on 404."""
        if not self.session:
            logger.error("Session not initialized for REST client")
            raise RestClientError("Session is not initialized.")

        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 404:
                    return None
                response.raise_for_status()
                if response.status == 204:
                    return {}
                return await response.json()
        except aiohttp.ClientResponseError as e:
            logger.error(
                "HTTP error during request",
                url=url,
                method=method,
                status=e.status,
                message=e.message,
                error=str(e),
            )
            raise RestClientError(
                f"HTTP Error {e.status} for {url}: {e.message}"
            ) from e
        except aiohttp.ClientError as e:
            logger.error("Client request error", url=url, method=method, error=str(e))
            raise RestClientError(f"Request failed for {url}: {str(e)}") from e
        except Exception as e:
            logger.error(
                "Unexpected error during request processing",
                url=url,
                method=method,
                error=str(e),
                exc_info=True,
            )
            raise RestClientError(f"Unexpected error for {url}: {str(e)}") from e

    def _parse_response(self, response_data: Any, model_cls: type, context: dict):
        """Parse response data into a Pydantic model, handling validation errors."""
        try:
            if isinstance(response_data, list):
                return [model_cls(**item) for item in response_data]
            elif isinstance(response_data, dict):
                return model_cls(**response_data)
            else:
                logger.error(
                    "Cannot parse non-dict/list response data",
                    data_type=type(response_data),
                    model=model_cls.__name__,
                    context=context,
                )
                raise RestClientError(
                    f"Cannot parse {type(response_data)} into {model_cls.__name__}"
                )
        except ValidationError as e:
            logger.error(
                "API response validation failed",
                model=model_cls.__name__,
                errors=e.errors(),
                data=response_data,
                context=context,
            )
            raise RestClientError(
                f"API response validation failed for {model_cls.__name__}: {e}"
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error during response parsing",
                model=model_cls.__name__,
                error=str(e),
                data=response_data,
                context=context,
                exc_info=True,
            )
            raise RestClientError(
                f"Unexpected parsing error for {model_cls.__name__}: {str(e)}"
            ) from e

    async def _get_user(self, telegram_id: int) -> Optional[TelegramUserRead]:
        """(Private) Get user by telegram_id."""
        response_data = await self._make_request(
            "GET", "/users/by-telegram-id/", params={"telegram_id": telegram_id}
        )
        if response_data is None:
            return None
        return self._parse_response(
            response_data,
            TelegramUserRead,
            context={"telegram_id": telegram_id, "method": "_get_user"},
        )

    async def _create_user(
        self, telegram_id: int, username: Optional[str] = None
    ) -> TelegramUserRead:
        """(Private) Create new user."""
        payload = TelegramUserCreate(telegram_id=telegram_id, username=username)
        response_data = await self._make_request(
            "POST", "/users/", json=payload.model_dump()
        )
        if response_data is None:
            logger.error(
                "Create user request returned None unexpectedly",
                telegram_id=telegram_id,
            )
            raise RestClientError("Failed to create user: No response data")
        return self._parse_response(
            response_data,
            TelegramUserRead,
            context={"telegram_id": telegram_id, "method": "_create_user"},
        )

    async def get_or_create_user(
        self, telegram_id: int, username: Optional[str] = None
    ) -> TelegramUserRead:
        """Get or create user."""
        user = await self._get_user(telegram_id)
        if user:
            # logger.info("Found existing user", telegram_id=telegram_id) # Less verbose logging
            return user
        logger.info("Creating new user", telegram_id=telegram_id)
        return await self._create_user(telegram_id, username)

    async def get_user_by_id(self, user_id: int) -> Optional[TelegramUserRead]:
        """Get user by user_id."""
        response_data = await self._make_request("GET", f"/users/{user_id}")
        if response_data is None:
            return None
        return self._parse_response(
            response_data,
            TelegramUserRead,
            context={"user_id": user_id, "method": "get_user_by_id"},
        )

    async def list_secretaries(self) -> List[AssistantRead]:
        """Get a list of available secretaries."""
        response_data = await self._make_request("GET", "/secretaries/")
        if response_data is None:
            logger.warning("List secretaries endpoint returned None, expected list")
            return []
        secretaries = self._parse_response(
            response_data, AssistantRead, context={"method": "list_secretaries"}
        )
        # logger.info("Retrieved secretaries list", count=len(secretaries)) # Less verbose logging
        return secretaries

    async def set_user_secretary(
        self, user_id: int, secretary_id: UUID
    ) -> UserSecretaryLinkRead:
        """Assign a secretary to a user."""
        try:
            response_data = await self._make_request(
                "POST", f"/users/{user_id}/secretary/{secretary_id}"
            )
            if response_data is None:
                logger.error(
                    "Set user secretary request returned None unexpectedly",
                    user_id=user_id,
                    secretary_id=secretary_id,
                )
                raise RestClientError("Failed to set secretary: No response data")
            link_data = self._parse_response(
                response_data,
                UserSecretaryLinkRead,
                context={
                    "user_id": user_id,
                    "secretary_id": secretary_id,
                    "method": "set_user_secretary",
                },
            )
            logger.info(
                "Successfully set secretary for user",
                user_id=user_id,
                secretary_id=secretary_id,
            )
            return link_data
        except (
            ValidationError
        ) as e:  # Keep specific validation handling here if needed, else rely on _parse_response
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
        """Get the currently assigned secretary for a user."""
        response_data = await self._make_request("GET", f"/users/{user_id}/secretary")
        if response_data is None:
            # logger.info("No active secretary found for user", user_id=user_id) # Less verbose logging
            return None
        secretary_data = self._parse_response(
            response_data,
            AssistantRead,
            context={"user_id": user_id, "method": "get_user_secretary"},
        )
        # logger.info("Found active secretary for user", user_id=user_id, secretary_id=secretary_data.id) # Less verbose
        return secretary_data

    async def get_assistant_by_id(self, assistant_id: UUID) -> Optional[AssistantRead]:
        """Get assistant details by assistant_id."""
        response_data = await self._make_request("GET", f"/assistants/{assistant_id}")
        if response_data is None:
            return None
        return self._parse_response(
            response_data,
            AssistantRead,
            context={"assistant_id": assistant_id, "method": "get_assistant_by_id"},
        )

    async def create_message(
        self,
        user_id: int,
        assistant_id: UUID,
        role: str,
        content: str,
        content_type: str,  # e.g., "text", "image_url"
        status: Optional[str] = None,
        # Potentially add other fields like message_type, status based on actual API
    ) -> Optional[MessageRead]:
        """Create a new message via the REST API."""
        # Prepare payload dictionary first, then pass to MessageCreate
        payload_dict = {
            "user_id": user_id,
            "assistant_id": assistant_id, # MessageCreate expects UUID, model_dump will handle serialization
            "role": role,
            "content": content,
            "content_type": content_type,
            # status and tool_call_id will use defaults from MessageBase if not provided
        }
        if status is not None: # Add status to payload if provided
            payload_dict["status"] = status
        
        # Use MessageCreate schema to build and validate the payload
        try:
            message_payload = MessageCreate(**payload_dict)
        except ValidationError as e:
            logger.error(
                "Validation error creating MessageCreate payload",
                payload_dict=payload_dict,
                errors=e.errors(),
            )
            raise RestClientError(f"Client-side validation failed for MessageCreate: {e}") from e

        response_data = await self._make_request(
            "POST", "/messages/", json=message_payload.model_dump(mode="json", exclude_none=True) # Use model_dump with mode="json"
        )

        if response_data is None:
            logger.error(
                "Create message request returned None unexpectedly (e.g. 404 or non-JSON 204)",
                payload=message_payload.model_dump(mode="json", exclude_none=True),
            )
            # If a 204 No Content is a valid successful response for message creation,
            # this logic might need adjustment. For now, assume None means an issue or unexpected 404.
            return None # Or raise RestClientError if None is always an error for POST /messages/

        return self._parse_response(
            response_data,
            MessageRead,
            context={"payload": message_payload.model_dump(mode="json", exclude_none=True), "method": "create_message"},
        )

    async def ping(self) -> bool:
        """Check if the REST service is healthy."""
        try:
            if not self.session:
                logger.error("Session not initialized before ping")
                raise RestClientError(
                    "Session is not initialized for ping."
                )  # Be explicit

            async with self.session.get(f"{self.base_url}/health") as response:
                response.raise_for_status()
                result = await response.json()
                if isinstance(result, dict) and result.get("status") == "healthy":
                    # logger.debug("REST service ping successful.") # Less verbose logging
                    return True
                else:
                    logger.warning(
                        "REST service ping returned unexpected status",
                        response_content=result,
                    )
                    return False
        except Exception as e:
            logger.error("REST service ping failed", error=str(e))
            return False

    async def close(self) -> None:
        """Close the aiohttp session if it exists and is open."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("REST Client session closed.")
        else:
            logger.debug(
                "REST Client close called but session was None or already closed."
            )
