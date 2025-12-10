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

    Note: Summary is now kept in-memory only (updated by summarize_history_node).
    Memory retrieval is handled by retrieve_memories_node via RAG service.
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

    # Load historical messages
    messages: list[BaseMessage] = []
    try:
        raw_messages = await rest_client.get_messages(
            user_id=user_id,
            assistant_id=assistant_id_str,
            limit=history_limit,
            status="processed",
            sort_by="id",
            sort_order="asc",
        )

        # Convert to BaseMessage objects
        messages = [_convert_db_message_to_langchain(msg) for msg in raw_messages]
        logger.info(
            f"Loaded {len(messages)} recent messages for user {user_id}",
            extra=log_extra,
        )
    except Exception as e:
        logger.error(f"Error loading messages: {str(e)}", extra=log_extra)

    # Prepare the updated state
    # Historical messages first (sorted by id in DB), then incoming message
    initial_message = state.get("initial_message")
    initial_message_id = state.get("initial_message_id")

    # Set DB ID on initial_message if available
    if initial_message and initial_message_id:
        initial_message.id = str(initial_message_id)

    full_context = messages + [initial_message] if initial_message else messages

    logger.info(
        f"Loaded context contains {len(full_context)} messages", extra=log_extra
    )

    return {
        "messages": full_context,
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
