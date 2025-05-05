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
    """Lists available secretaries via REST API."""
    logger.info("Listing available secretaries")
    try:
        response_data = await rest.list_secretaries()
        # Assuming response_data is a list of dicts or validated elsewhere
        # Use parse_obj_as for Pydantic v1 or TypeAdapter for Pydantic v2
        # For simplicity, assume REST client returns list of AssistantRead or similar
        # Let's assume it returns a list of dicts that need parsing
        # from pydantic import parse_obj_as # Pydantic v1
        # secretaries = parse_obj_as(List[AssistantRead], response_data)
        # Or handle parsing based on actual RestClient implementation
        if isinstance(response_data, list):  # Basic check
            # This part depends heavily on how RestClient returns data and Pydantic version
            # Assuming RestClient has handled parsing or returns data parsable by AssistantRead.model_validate
            try:
                # Pydantic v2 style validation
                secretaries = [
                    AssistantRead.model_validate(item) for item in response_data
                ]
            except Exception as pydantic_error:
                logger.error(
                    "Pydantic validation error for secretaries list",
                    data=response_data,
                    error=pydantic_error,
                )
                raise RestClientError(
                    f"Failed to parse secretaries list: {pydantic_error}"
                ) from pydantic_error

        else:
            logger.error(
                "Unexpected response format for secretaries list", data=response_data
            )
            raise RestClientError(
                f"Unexpected response format from /assistants/: {type(response_data)}"
            )

        logger.info("Successfully listed secretaries", count=len(secretaries))
        return secretaries
    except RestClientError as e:
        logger.error("REST Client Error listing secretaries", error=str(e))
        raise  # Re-raise the original exception
    except Exception as e:
        logger.error(
            "Unexpected error listing secretaries", error=str(e), exc_info=True
        )
        # Wrap unexpected errors in RestClientError or a custom service error
        raise RestClientError(f"Unexpected error listing secretaries: {e}") from e


# --- NEW FUNCTION ---
import re  # For Markdown escaping

from clients.telegram import TelegramClient
from keyboards.secretary_selection import create_secretary_selection_keyboard


def escape_markdown_v2(text: str) -> str:
    """Escapes characters for Telegram MarkdownV2 parse mode."""
    # Characters to escape: _ * [ ] ( ) ~ ` > # + - = | { } . !
    # Use re.escape to handle these characters within a regex pattern
    # The pattern looks for any character in the set and adds a backslash before it
    escape_chars = r"_*[]()~`>#+\-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


async def prompt_secretary_selection(
    telegram: TelegramClient,
    rest: RestClient,
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
    secretaries: List[AssistantRead] = []
    try:
        secretaries = await list_available_secretaries(rest)
    except RestClientError as e:
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
            "К сожалению, сейчас нет доступных секретарей для выбора. Попробуйте позже.",
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
