import logging
from typing import List, Optional, Sequence, Tuple

from assistants.langgraph.constants import (
    HISTORY_SUMMARY_NAME,
    SYSTEM_PROMPT_NAME,
    USER_FACTS_NAME,
)
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)


def _filter_system_messages_and_get_summary(
    messages: Sequence[BaseMessage],
) -> Tuple[Optional[SystemMessage], List[BaseMessage]]:
    """Filters system messages, logs them, and extracts the first history summary."""
    first_history_summary: Optional[SystemMessage] = None
    potentially_valid_messages: List[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            msg_name = getattr(msg, "name", None)
            msg_id = getattr(msg, "id", "N/A")
            if msg_name == SYSTEM_PROMPT_NAME:
                logger.warning(f"Discarding sys prompt (id={msg_id})")
            elif msg_name == USER_FACTS_NAME:
                logger.warning(f"Discarding user facts (id={msg_id})")
            elif msg_name == HISTORY_SUMMARY_NAME:
                if first_history_summary is None:
                    logger.debug(f"Found first history summary (id={msg_id})")
                    first_history_summary = msg  # Keep track, add later
                else:
                    logger.warning(f"Discarding extra history summary (id={msg_id})")
            else:  # Assume other SystemMessages are errors
                logger.error(
                    f"Discarding likely error SystemMessage (id={msg_id}, name={msg_name})"
                )
        else:
            # Keep Human, AI, Tool for now
            potentially_valid_messages.append(msg)
    return first_history_summary, potentially_valid_messages


def _is_ai_message_calling_tool(ai_message: BaseMessage, tool_call_id: str) -> bool:
    """Checks if the AI message contains the specified tool_call_id."""
    if not isinstance(ai_message, AIMessage) or not ai_message.tool_calls:
        return False
    for tc in ai_message.tool_calls:
        if isinstance(tc, dict) and tc.get("id") == tool_call_id:
            return True
    return False


def _log_critical_last_orphan_tool_message(messages: List[BaseMessage]) -> bool:
    """Checks and logs if the last message is an orphaned ToolMessage. Returns True if logged."""
    if not messages:
        return False

    last_msg = messages[-1]
    if not isinstance(last_msg, ToolMessage):
        return False

    tool_call_id_last = getattr(last_msg, "tool_call_id", None)
    if not tool_call_id_last:
        # ToolMessage without tool_call_id is invalid anyway, treat as orphan
        logger.error(
            f"CRITICAL: Last message is ToolMessage (id={getattr(last_msg, 'id', 'N/A')}) but has no tool_call_id."
        )
        return True

    is_last_orphan = True
    if len(messages) > 1:
        prev_msg = messages[-2]
        if _is_ai_message_calling_tool(prev_msg, tool_call_id_last):
            is_last_orphan = False

    if is_last_orphan:
        logger.error(
            f"CRITICAL: Last message is orphaned ToolMessage (id={getattr(last_msg, 'id', 'N/A')}, "
            f"tool_call_id={tool_call_id_last}). Expected tool result may be missing."
        )
        return True

    return False  # Not an orphan or not the last message


def _validate_and_filter_tool_message_pairs(
    messages: List[BaseMessage], logged_last_orphan_error: bool
) -> List[BaseMessage]:
    """Validates AIMessage->ToolMessage pairs and filters orphans."""
    final_validated_messages: List[BaseMessage] = []
    for i, current_msg in enumerate(messages):
        if isinstance(current_msg, ToolMessage):
            tool_call_id = getattr(current_msg, "tool_call_id", None)
            is_valid_pair = False
            if i > 0 and tool_call_id:
                prev_msg = messages[i - 1]
                if _is_ai_message_calling_tool(prev_msg, tool_call_id):
                    is_valid_pair = True

            if is_valid_pair:
                final_validated_messages.append(current_msg)
            else:
                # Log warning only if it wasn't the last message already logged as critical error
                is_last_message = i == len(messages) - 1
                if not (is_last_message and logged_last_orphan_error):
                    logger.warning(
                        f"Discarding orphaned ToolMessage (id={getattr(current_msg, 'id', 'N/A')}, "
                        f"tool_call_id={tool_call_id}) due to missing/incorrect preceding AIMessage."
                    )
                # Do not append the orphan/invalid message
        else:
            # Keep non-ToolMessages (Human, AI)
            final_validated_messages.append(current_msg)
    return final_validated_messages


def custom_message_reducer(
    current_state_messages: Optional[Sequence[BaseMessage]],
    new_messages: Optional[Sequence[BaseMessage]],
) -> List[BaseMessage]:
    """
    Custom reducer for the 'messages' field in AssistantState.

    Orchestrates filtering and validation steps:
    1. Combines messages.
    2. Filters system messages and gets the first summary.
    3. Checks for a critical orphaned ToolMessage at the end.
    4. Validates AIMessage->ToolMessage pairs, removing orphans.
    5. Prepends the summary.
    """
    # --- Added None checks ---
    left = current_state_messages if current_state_messages is not None else []
    right = new_messages if new_messages is not None else []
    # --------------------------

    # 1. Combine messages using the checked variables
    combined_messages = add_messages(left, right)
    if not combined_messages:
        return []

    # 2. Filter system messages, identify first summary
    (
        first_history_summary,
        potentially_valid_messages,
    ) = _filter_system_messages_and_get_summary(combined_messages)

    # 3. Check critical case: last message is orphaned ToolMessage
    logged_last_orphan_error = _log_critical_last_orphan_tool_message(
        potentially_valid_messages
    )

    # 4. Validate ToolMessages based on strict preceding AIMessage
    final_validated_messages = _validate_and_filter_tool_message_pairs(
        potentially_valid_messages, logged_last_orphan_error
    )

    # 5. Prepend the first history summary if found
    final_messages: List[BaseMessage] = []
    if first_history_summary:
        final_messages.append(first_history_summary)
        logger.debug(
            f"Prepended history summary (id={getattr(first_history_summary, 'id', 'N/A')})"
        )

    final_messages.extend(final_validated_messages)

    logger.debug(
        f"Custom reducer produced {len(final_messages)} messages after all filtering and validation."
    )
    return final_messages
