from typing import List, Optional
from uuid import UUID

import structlog
from clients.rest import RestClient, RestClientError

from shared_models.api_schemas import AssistantRead, TelegramUserRead

logger = structlog.get_logger()


async def get_or_create_telegram_user(
    rest: RestClient, telegram_id: int, username: Optional[str]
) -> TelegramUserRead:
    """Gets or creates a user via the REST API.

    Raises:
        RestClientError: If the API call fails.
    Returns:
        The TelegramUserRead object.
    """
    # Exceptions from rest client are expected to be handled by the caller
    logger.debug("Calling rest.get_or_create_user", telegram_id=telegram_id)
    user = await rest.get_or_create_user(telegram_id, username)
    # get_or_create_user should not return None on success
    if not user:
        # This case indicates an unexpected issue with the REST API or client logic
        logger.error(
            "get_or_create_user returned None unexpectedly", telegram_id=telegram_id
        )
        raise RestClientError(
            "Failed to get or create user: received unexpected None response"
        )
    return user


async def get_user_by_telegram_id(
    rest: RestClient, telegram_id: int
) -> Optional[TelegramUserRead]:
    """Retrieve a user by their Telegram ID."""
    logger.info("Getting user by Telegram ID", telegram_id=telegram_id)
    # Method was removed from RestClient as it duplicates get_user
    # Use the private method _get_user instead
    return await rest._get_user(telegram_id)


async def get_assigned_secretary(
    rest: RestClient, user_id: UUID
) -> Optional[AssistantRead]:
    """Gets the assigned secretary for a user via the REST API.

    Handles 404 by returning None.
    Raises:
        RestClientError: For non-404 errors.
    Returns:
        The AssistantRead object or None if not assigned (404).
    """
    # Let the handler deal with specific error codes like 404 vs other errors
    logger.debug("Calling rest.get_user_secretary", user_id=user_id)
    return await rest.get_user_secretary(user_id)


async def set_user_secretary(
    rest: RestClient, user_id: UUID, secretary_id: UUID
) -> None:
    """Assigns a secretary to a user via the REST API.

    Raises:
        RestClientError: If the API call fails.
    """
    # Exceptions from rest client are expected to be handled by the caller
    logger.debug(
        "Calling rest.set_user_secretary", user_id=user_id, secretary_id=secretary_id
    )
    # Assuming the client method raises RestClientError on failure
    await rest.set_user_secretary(user_id, secretary_id)
    logger.info(
        "Successfully called rest.set_user_secretary",
        user_id=user_id,
        secretary_id=secretary_id,
    )


async def list_available_secretaries(rest: RestClient) -> List[AssistantRead]:
    """Lists all available secretaries via the REST API.

    Raises:
        RestClientError: If the API call fails.
    Returns:
        A list of AssistantRead objects.
    """
    # Exceptions from rest client are expected to be handled by the caller
    logger.debug("Calling rest.list_secretaries")
    secretaries = await rest.list_secretaries()
    return secretaries
