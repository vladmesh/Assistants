import logging
from typing import Any, Dict, List, Optional

from assistants.langgraph.state import AssistantState
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)

# Constants for message loading
DEFAULT_HISTORY_LIMIT = 50  # Maximum number of past messages to load


async def load_context_node(
    state: AssistantState,
    rest_client: RestServiceClient,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
) -> Dict[str, Any]:
    """
    Loads the conversation context from the database:
    1. Historical messages (up to a limit)
    2. Current summary
    3. User facts

    Updates the AssistantState with the loaded context.
    """
    logger.info("[load_context_node] Loading context from database")

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

    # Get current message to determine where to load history from
    current_messages = state.get("messages", [])
    if not current_messages:
        logger.warning(
            "No current message in state, loading context may be incomplete.",
            extra=log_extra,
        )

    # 1. Get the latest summary first
    summary = None
    try:
        summary = await rest_client.get_user_summary(user_id, assistant_id_str)
        if summary:
            logger.info(
                f"Loaded summary (ID: {summary.id}) for user {user_id}", extra=log_extra
            )
        else:
            logger.info(f"No summary found for user {user_id}", extra=log_extra)
    except Exception as e:
        logger.error(f"Error loading summary: {str(e)}", extra=log_extra)

    # 2. Load historical messages
    messages: List[BaseMessage] = []
    last_message_id = None
    if summary and summary.last_message_id_covered:
        # If we have a summary, load messages after the last summarized message
        try:
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
                f"Loaded {len(messages)} messages after summary (last_id: {summary.last_message_id_covered})",
                extra=log_extra,
            )
        except Exception as e:
            logger.error(
                f"Error loading messages after summary: {str(e)}", extra=log_extra
            )
    else:
        # If no summary, just load the most recent messages
        try:
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

    # 3. Load user facts
    user_facts = []
    try:
        facts_result = await rest_client.get_user_facts(user_id)
        user_facts = facts_result if facts_result else []
        logger.info(f"Loaded {len(user_facts)} user facts", extra=log_extra)
    except Exception as e:
        logger.error(f"Error loading user facts: {str(e)}", extra=log_extra)

    # 4. Prepare the updated state
    # В полный контекст сначала идут исторические сообщения (отсортированные в БД по id),
    # затем входящее сообщение
    full_context = messages + list(current_messages)

    # Отладочный вывод сообщений
    logger.debug(f"Context messages ({len(full_context)} total):", extra=log_extra)
    for i, msg in enumerate(full_context):
        msg_type = type(msg).__name__
        msg_id = getattr(msg, "additional_kwargs", {}).get("db_id", "no_db_id")
        content_preview = getattr(msg, "content", "")[:30].replace("\n", " ") + (
            "..." if len(getattr(msg, "content", "")) > 30 else ""
        )
        logger.debug(
            f"  [{i}] Type={msg_type}, DB_ID={msg_id}, Content='{content_preview}'",
            extra=log_extra,
        )

    logger.info(
        f"Loaded context contains {len(full_context)} messages", extra=log_extra
    )

    # Return the updated state
    return {
        "messages": full_context,
        "current_summary_content": summary.summary_text if summary else None,
        "user_facts": user_facts,
    }


def _convert_db_message_to_langchain(db_message) -> BaseMessage:
    """Convert a database message to a LangChain message class."""
    content = db_message.content or ""

    # Map role to appropriate LangChain message class
    if db_message.role == "human":
        msg = HumanMessage(content=content)
    elif db_message.role == "assistant":
        msg = AIMessage(content=content)
    elif db_message.role in ["tool_request", "tool_response"]:
        # For tool messages, we might need additional processing based on your schema
        msg = ToolMessage(
            content=content,
            tool_call_id=str(db_message.tool_call_id)
            if db_message.tool_call_id
            else None,
        )
    else:
        # Default fallback - log warning about unknown role
        logger.warning(
            f"Unknown message role: {db_message.role}, treating as human message"
        )
        msg = HumanMessage(content=content)

    # Сохраняем ID из базы в additional_kwargs для отладки
    if hasattr(db_message, "id") and db_message.id:
        msg.additional_kwargs["db_id"] = db_message.id

    return msg
