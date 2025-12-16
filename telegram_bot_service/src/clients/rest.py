"""REST client for telegram_bot_service using BaseServiceClient."""

from uuid import UUID

from pydantic import ValidationError
from shared_models import (
    BaseServiceClient,
    ClientConfig,
    ServiceClientError,
    ServiceResponseError,
    get_logger,
)
from shared_models.api_schemas import (
    AssistantRead,
    MessageCreate,
    MessageRead,
    TelegramUserCreate,
    TelegramUserRead,
    UserSecretaryLinkRead,
)

from config.settings import settings

logger = get_logger(__name__)


# Re-export errors for backward compatibility
RestClientError = ServiceClientError


class TelegramRestClient(BaseServiceClient):
    """REST client for telegram_bot_service."""

    def __init__(self, base_url: str | None = None):
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
            base_url=base_url or settings.rest_service_url,
            service_name="telegram_bot_service",
            target_service="rest_service",
            config=config,
        )

    def _parse_response(self, response_data, model_cls: type, context: dict):
        """Parse response data into a Pydantic model."""
        try:
            if isinstance(response_data, list):
                return [model_cls.model_validate(item) for item in response_data]
            elif isinstance(response_data, dict):
                return model_cls.model_validate(response_data)
            else:
                logger.error(
                    "Cannot parse non-dict/list response data",
                    data_type=type(response_data).__name__,
                    model=model_cls.__name__,
                    context=context,
                )
                raise ServiceClientError(
                    f"Cannot parse {type(response_data)} into {model_cls.__name__}"
                )
        except ValidationError as e:
            logger.error(
                "API response validation failed",
                model=model_cls.__name__,
                errors=e.errors(),
                context=context,
            )
            raise ServiceClientError(
                f"API response validation failed for {model_cls.__name__}: {e}"
            ) from e

    async def _get_user(self, telegram_id: int) -> TelegramUserRead | None:
        """Get user by telegram_id."""
        try:
            response_data = await self.request(
                "GET", "/api/users/by-telegram-id/", params={"telegram_id": telegram_id}
            )
            if response_data is None:
                return None
            return self._parse_response(
                response_data,
                TelegramUserRead,
                context={"telegram_id": telegram_id, "method": "_get_user"},
            )
        except ServiceResponseError as e:
            if e.status_code == 404:
                return None
            raise

    async def _create_user(
        self, telegram_id: int, username: str | None = None
    ) -> TelegramUserRead:
        """Create new user."""
        payload = TelegramUserCreate(telegram_id=telegram_id, username=username)
        response_data = await self.request(
            "POST", "/api/users/", json=payload.model_dump()
        )
        if response_data is None:
            logger.error(
                "Create user request returned None unexpectedly",
                telegram_id=telegram_id,
            )
            raise ServiceClientError("Failed to create user: No response data")
        return self._parse_response(
            response_data,
            TelegramUserRead,
            context={"telegram_id": telegram_id, "method": "_create_user"},
        )

    async def get_or_create_user(
        self, telegram_id: int, username: str | None = None
    ) -> TelegramUserRead:
        """Get or create user."""
        user = await self._get_user(telegram_id)
        if user:
            return user
        logger.info("Creating new user", telegram_id=telegram_id)
        return await self._create_user(telegram_id, username)

    async def get_user_by_id(self, user_id: int) -> TelegramUserRead | None:
        """Get user by user_id."""
        try:
            response_data = await self.request("GET", f"/api/users/{user_id}")
            if response_data is None:
                return None
            return self._parse_response(
                response_data,
                TelegramUserRead,
                context={"user_id": user_id, "method": "get_user_by_id"},
            )
        except ServiceResponseError as e:
            if e.status_code == 404:
                return None
            raise

    async def list_secretaries(self) -> list[AssistantRead]:
        """Get a list of available secretaries."""
        response_data = await self.request("GET", "/api/secretaries/")
        if response_data is None:
            logger.warning("List secretaries endpoint returned None, expected list")
            return []
        return self._parse_response(
            response_data, AssistantRead, context={"method": "list_secretaries"}
        )

    async def set_user_secretary(
        self, user_id: int, secretary_id: UUID
    ) -> UserSecretaryLinkRead:
        """Assign a secretary to a user."""
        response_data = await self.request(
            "POST", f"/api/users/{user_id}/secretary/{secretary_id}"
        )
        if response_data is None:
            logger.error(
                "Set user secretary request returned None unexpectedly",
                user_id=user_id,
                secretary_id=str(secretary_id),
            )
            raise ServiceClientError("Failed to set secretary: No response data")
        link_data = self._parse_response(
            response_data,
            UserSecretaryLinkRead,
            context={
                "user_id": user_id,
                "secretary_id": str(secretary_id),
                "method": "set_user_secretary",
            },
        )
        logger.info(
            "Successfully set secretary for user",
            user_id=user_id,
            secretary_id=str(secretary_id),
        )
        return link_data

    async def get_user_secretary(self, user_id: int) -> AssistantRead | None:
        """Get the currently assigned secretary for a user."""
        try:
            response_data = await self.request("GET", f"/api/users/{user_id}/secretary")
            if response_data is None:
                return None
            return self._parse_response(
                response_data,
                AssistantRead,
                context={"user_id": user_id, "method": "get_user_secretary"},
            )
        except ServiceResponseError as e:
            if e.status_code == 404:
                return None
            raise

    async def get_assistant_by_id(self, assistant_id: UUID) -> AssistantRead | None:
        """Get assistant details by assistant_id."""
        try:
            response_data = await self.request("GET", f"/api/assistants/{assistant_id}")
            if response_data is None:
                return None
            return self._parse_response(
                response_data,
                AssistantRead,
                context={
                    "assistant_id": str(assistant_id),
                    "method": "get_assistant_by_id",
                },
            )
        except ServiceResponseError as e:
            if e.status_code == 404:
                return None
            raise

    async def create_message(
        self,
        user_id: int,
        assistant_id: UUID,
        role: str,
        content: str,
        content_type: str,
        status: str | None = None,
    ) -> MessageRead | None:
        """Create a new message via the REST API."""
        payload_dict = {
            "user_id": user_id,
            "assistant_id": assistant_id,
            "role": role,
            "content": content,
            "content_type": content_type,
        }
        if status is not None:
            payload_dict["status"] = status

        try:
            message_payload = MessageCreate(**payload_dict)
        except ValidationError as e:
            logger.error(
                "Validation error creating MessageCreate payload",
                payload_dict=payload_dict,
                errors=e.errors(),
            )
            raise ServiceClientError(
                f"Client-side validation failed for MessageCreate: {e}"
            ) from e

        response_data = await self.request(
            "POST",
            "/api/messages/",
            json=message_payload.model_dump(mode="json", exclude_none=True),
        )

        if response_data is None:
            logger.error(
                "Create message returned None",
                payload=message_payload.model_dump(mode="json", exclude_none=True),
            )
            return None

        return self._parse_response(
            response_data,
            MessageRead,
            context={
                "payload": message_payload.model_dump(mode="json", exclude_none=True),
                "method": "create_message",
            },
        )

    async def ping(self) -> bool:
        """Check if the REST service is healthy."""
        try:
            response_data = await self.request("GET", "/health")
            if (
                isinstance(response_data, dict)
                and response_data.get("status") == "healthy"
            ):
                return True
            logger.warning(
                "REST service ping returned unexpected status",
                response_content=response_data,
            )
            return False
        except Exception as e:
            logger.error("REST service ping failed", error=str(e))
            return False


# Alias for backward compatibility
RestClient = TelegramRestClient
