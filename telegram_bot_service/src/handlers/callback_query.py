from typing import Any

import structlog

from clients.telegram import TelegramClient

logger = structlog.get_logger()


async def handle_callback_query(**context: Any) -> None:
    """Handles callback queries that don't match specific command patterns."""
    telegram: TelegramClient = context["telegram"]
    query_id: str = context["query_id"]
    data: str = context.get("data", "(no data)")  # Safely get data
    chat_id = context.get("chat_id", "(unknown chat)")
    user_id_str = context.get("user_id_str", "(unknown user)")

    logger.warning(
        "Received unhandled callback query",
        query_id=query_id,
        data=data,
        chat_id=chat_id,
        user_id=user_id_str,
    )

    try:
        # Answer the callback query to remove the loading state on the button
        await telegram.answer_callback_query(
            query_id, text="Действие пока не поддерживается."
        )
    except Exception as e:
        logger.error(
            "Failed to answer unhandled callback query",
            query_id=query_id,
            error=str(e),
        )
