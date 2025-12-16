import re  # For Markdown escaping
from uuid import UUID

from shared_models import ServiceClientError, get_logger
from shared_models.api_schemas import AssistantRead, TelegramUserRead

from clients.rest import TelegramRestClient
from clients.telegram import TelegramClient
from keyboards.secretary_selection import create_secretary_selection_keyboard

logger = get_logger(__name__)

# Alias for backward compatibility
RestClientError = ServiceClientError


async def get_or_create_telegram_user(
    rest: TelegramRestClient, telegram_id: int, username: str | None
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
    rest: TelegramRestClient, telegram_id: int
) -> TelegramUserRead | None:
    """Retrieve a user by their Telegram ID."""
    logger.info("Getting user by Telegram ID", telegram_id=telegram_id)
    # Method was removed from RestClient as it duplicates get_user
    # Use the private method _get_user instead
    return await rest._get_user(telegram_id)


async def get_assigned_secretary(
    rest: TelegramRestClient, user_id: UUID
) -> AssistantRead | None:
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
    rest: TelegramRestClient, user_id: UUID, secretary_id: UUID
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


async def list_available_secretaries(rest: TelegramRestClient) -> list[AssistantRead]:
    """Lists available secretaries via REST API."""
    logger.info("Listing available secretaries")
    try:
        # TelegramRestClient.list_secretaries() returns list[AssistantRead]
        secretaries = await rest.list_secretaries()
        logger.info("Successfully listed secretaries", count=len(secretaries))
        return secretaries
    except ServiceClientError as e:
        logger.error("REST Client Error listing secretaries", error=str(e))
        raise
    except Exception as e:
        logger.error(
            "Unexpected error listing secretaries", error=str(e), exc_info=True
        )
        raise ServiceClientError(f"Unexpected error listing secretaries: {e}") from e


def escape_markdown_v2(text: str) -> str:
    """Escapes characters for Telegram MarkdownV2 parse mode."""
    # Characters to escape: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # Use re.escape to handle these characters within a regex pattern
    # The pattern looks for any character in the set and adds a backslash before it
    escape_chars = r"_*[]()~`>#+\-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


async def prompt_secretary_selection(
    telegram: TelegramClient,
    rest: TelegramRestClient,
    chat_id: int,
    prompt_message: str,
    user_id_for_log: str | int | None = None,
) -> bool:
    """
    Fetches secretaries, formats selection message, creates keyboard, and sends it.

    Args:
        telegram: Telegram client instance.
        rest: REST client instance.
        chat_id: Target chat ID.
        prompt_message: The initial text to show before the list.
        user_id_for_log: User identifier for logging purposes.

    Returns:
        True if the prompt was sent successfully, False otherwise.
    """
    secretaries: list[AssistantRead] = []
    try:
        secretaries = await list_available_secretaries(rest)
    except RestClientError:
        # Error already logged in list_available_secretaries, just notify user
        await telegram.send_message(
            chat_id,
            "Не удалось загрузить список секретарей. Попробуйте позже.",
        )
        return False

    if not secretaries:
        logger.warning(
            "No secretaries found, cannot prompt user.",
            chat_id=chat_id,
            user_id=user_id_for_log,
        )
        await telegram.send_message(
            chat_id,
            (
                "К сожалению, сейчас нет доступных секретарей для выбора. "
                "Попробуйте позже."
            ),
        )
        return False

    # Format the message text with secretary descriptions
    message_lines = [escape_markdown_v2(prompt_message), ""]
    for i, secretary in enumerate(secretaries, start=1):
        safe_name = escape_markdown_v2(secretary.name)
        safe_description = escape_markdown_v2(secretary.description or "(Нет описания)")

        message_lines.append(f"{i}\\. __{safe_name}__")
        message_lines.append(f"   _{safe_description}_")
        message_lines.append("")

    message_text = "\n".join(message_lines)

    # Create inline keyboard (with only names)
    keyboard_buttons = create_secretary_selection_keyboard(secretaries)

    # Send message with descriptions and inline keyboard
    try:
        await telegram.send_message_with_inline_keyboard(
            chat_id=chat_id,
            text=message_text,
            keyboard=keyboard_buttons,
            parse_mode="MarkdownV2",
        )
        logger.info(
            "Secretary selection prompt sent",
            chat_id=chat_id,
            user_id=user_id_for_log,
            count=len(secretaries),
        )
        return True
    except Exception as e:
        logger.error(
            "Failed to send secretary selection prompt via Telegram",
            chat_id=chat_id,
            user_id=user_id_for_log,
            error=str(e),
            exc_info=True,
        )
        # Attempt to send a simple error message if the complex one failed
        try:
            await telegram.send_message(
                chat_id, "Произошла ошибка при отображении списка секретарей."
            )
        except Exception as e_inner:
            logger.error(
                "Failed even to send simple error message",
                chat_id=chat_id,
                user_id=user_id_for_log,
                error=str(e_inner),
            )
        return False


# --- END NEW FUNCTION ---
