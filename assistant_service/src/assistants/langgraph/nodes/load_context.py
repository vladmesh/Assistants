import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from assistants.langgraph.state import AssistantState
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)

# Constants for message loading
DEFAULT_HISTORY_LIMIT = 50  # Maximum number of past messages to load


async def load_context_node(
    state: AssistantState,
    rest_client: RestServiceClient,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> dict[str, Any]:
    """
    Loads the conversation context from the database:
    1. Historical messages (up to a limit)
    2. Current summary
    3. User facts

    Updates the AssistantState with the loaded context.
    """

    # Extract necessary IDs
    user_id_str = state.get("user_id", "")
    assistant_id_str = state.get("assistant_id", "")
    log_extra = state.get("log_extra", {})

    # Input validation
    if not user_id_str or not assistant_id_str:
        logger.error(
            "User ID or Assistant ID not found in state, cannot load context.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Convert user_id to int
    try:
        user_id = int(user_id_str)
    except ValueError:
        logger.error(
            f"Invalid User ID format '{user_id_str}', cannot load context.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # 1. Get the latest summary first
    summary = None
    try:
        summary = await rest_client.get_user_summary(user_id, assistant_id_str)
        if summary:
            logger.info(
                f"Loaded summary (ID: {summary.id}) for user {user_id}", extra=log_extra
            )
            print(f"Loaded summary: ID={summary.id}")
        else:
            logger.info(f"No summary found for user {user_id}", extra=log_extra)
            print("No summary found")
    except Exception as e:
        logger.error(f"Error loading summary: {str(e)}", extra=log_extra)
        print(f"Error loading summary: {e}")

    # 2. Load historical messages
    messages: list[BaseMessage] = []
    if summary and summary.last_message_id_covered:
        # If we have a summary, load messages after the last summarized message
        try:
            print(
                "Loading messages after summary "
                f"last_id: {summary.last_message_id_covered}"
            )
            raw_messages = await rest_client.get_messages(
                user_id=user_id,
                assistant_id=assistant_id_str,
                id_gt=summary.last_message_id_covered,
                limit=history_limit,
                status="processed",
                sort_by="id",  # Сортировка по id вместо timestamp
                sort_order="asc",
            )

            # Convert to BaseMessage objects
            messages = [_convert_db_message_to_langchain(msg) for msg in raw_messages]
            logger.info(
                (
                    f"Loaded {len(messages)} messages after summary "
                    f"(last_id: {summary.last_message_id_covered})"
                ),
                extra=log_extra,
            )
        except Exception as e:
            logger.error(
                f"Error loading messages after summary: {str(e)}", extra=log_extra
            )
            print(f"Error loading messages after summary: {e}")
    else:
        # If no summary, just load the most recent messages
        try:
            print("Loading most recent messages (no summary)")
            raw_messages = await rest_client.get_messages(
                user_id=user_id,
                assistant_id=assistant_id_str,
                limit=history_limit,
                status="processed",
                sort_by="id",  # Сортировка по id вместо timestamp
                sort_order="asc",
            )

            # Convert to BaseMessage objects
            messages = [_convert_db_message_to_langchain(msg) for msg in raw_messages]
            logger.info(
                f"Loaded {len(messages)} recent messages (no summary)", extra=log_extra
            )
        except Exception as e:
            logger.error(f"Error loading recent messages: {str(e)}", extra=log_extra)
            print(f"Error loading recent messages: {e}")

    # 3. Prepare the updated state
    # В полный контекст сначала идут исторические сообщения
    # (отсортированные в БД по id), затем входящее сообщение

    # Получаем initial_message_id, если он есть в state
    initial_message = state.get("initial_message")
    initial_message_id = state.get("initial_message_id")

    # Если у initial_message есть ID из БД, добавим его в id
    if initial_message and initial_message_id:
        initial_message.id = str(initial_message_id)

    full_context = messages + [initial_message] if initial_message else messages

    logger.info(
        f"Loaded context contains {len(full_context)} messages", extra=log_extra
    )

    # Return the updated state
    return {
        "messages": full_context,
        "current_summary_content": summary.summary_text if summary else None,
    }


def _convert_db_message_to_langchain(db_message) -> BaseMessage:
    """Convert a database message to a LangChain message class."""
    content = db_message.content or ""
    # Преобразуем ID из БД в строку для использования в качестве ID сообщения LangChain
    msg_id = str(db_message.id)

    logger.debug(
        f"Converting DB message: ID={msg_id}, Role={db_message.role}, "
        f"Content Preview={content[:30]}..."
    )

    # Map role to appropriate LangChain message class
    if db_message.role == "human":
        msg = HumanMessage(content=content, id=msg_id)
    elif db_message.role == "assistant":
        msg = AIMessage(content=content, id=msg_id)
    elif db_message.role == "tool":
        # For tool messages, we might need additional processing based on your schema
        msg = ToolMessage(
            content=content,
            tool_call_id=str(db_message.tool_call_id)
            if db_message.tool_call_id
            else None,
            id=msg_id,
        )
    else:
        # Default fallback - log warning about unknown role
        logger.warning(
            f"Unknown message role: {db_message.role}, treating as human message"
        )
        msg = HumanMessage(content=content, id=msg_id)

    if not hasattr(msg, "id") or msg.id is None:
        logger.warning("WARNING: Message has no ID attribute set")

    return msg
