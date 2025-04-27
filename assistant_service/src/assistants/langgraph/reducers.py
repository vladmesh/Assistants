import logging
from typing import List, Optional, Sequence

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)


def _filter_all_system_messages(
    messages: Sequence[BaseMessage],
) -> List[BaseMessage]:
    """Filters out ALL system messages, logging their details before discarding."""
    potentially_valid_messages: List[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            msg_name = getattr(msg, "name", "None")
            msg_id = getattr(msg, "id", "N/A")
            logger.warning(
                f"Discarding SystemMessage (id={msg_id}, name={msg_name}) in reducer."
            )
        else:
            potentially_valid_messages.append(msg)
    return potentially_valid_messages


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
    2. Filters out ALL system messages.
    3. Checks for a critical orphaned ToolMessage at the end.
    4. Validates AIMessage->ToolMessage pairs, removing orphans.
    """
    print("\n[DEBUG] Custom Reducer: ENTERED")
    left = current_state_messages if current_state_messages is not None else []
    right = new_messages if new_messages is not None else []

    # --- DEBUG PRINT: Show input lists ---
    print(f"[DEBUG] Custom Reducer: Input 'left' ({len(left)} messages):")
    for i, msg in enumerate(left):
        msg_id = getattr(msg, "id", "NO_ID")
        print(f"  L[{i}] Type={type(msg).__name__}, ID={msg_id}")
    print(f"[DEBUG] Custom Reducer: Input 'right' ({len(right)} messages):")
    for i, msg in enumerate(right):
        msg_id = getattr(msg, "id", "NO_ID")
        # Check specifically for RemoveMessage
        is_remove = isinstance(msg, RemoveMessage)
        print(
            f"  R[{i}] Type={type(msg).__name__}, ID={msg_id}"
            + (" (RemoveMessage)" if is_remove else "")
        )
    # ------------------------------------

    combined_messages = add_messages(left, right)
    # --- DEBUG PRINT: After add_messages ---
    print(
        f"[DEBUG] Custom Reducer: After add_messages ({len(combined_messages)} messages):"
    )
    for i, msg in enumerate(combined_messages):
        msg_id = getattr(msg, "id", "NO_ID")
        print(f"  C[{i}] Type={type(msg).__name__}, ID={msg_id}")
    # --------------------------------------

    if not combined_messages:
        print("[DEBUG] Custom Reducer: Combined messages empty, returning [].")
        return []

    potentially_valid_messages = _filter_all_system_messages(combined_messages)
    # --- DEBUG PRINT: After filter system ---
    print(
        f"[DEBUG] Custom Reducer: After _filter_all_system_messages ({len(potentially_valid_messages)} messages):"
    )
    for i, msg in enumerate(potentially_valid_messages):
        msg_id = getattr(msg, "id", "NO_ID")
        print(f"  P[{i}] Type={type(msg).__name__}, ID={msg_id}")
    # --------------------------------------

    logged_last_orphan_error = _log_critical_last_orphan_tool_message(
        potentially_valid_messages
    )
    # --- DEBUG PRINT: Logged last orphan? ---
    print(
        f"[DEBUG] Custom Reducer: Logged last orphan error? {logged_last_orphan_error}"
    )
    # ----------------------------------------

    final_validated_messages = _validate_and_filter_tool_message_pairs(
        potentially_valid_messages, logged_last_orphan_error
    )
    # --- DEBUG PRINT: After validate tool pairs ---
    print(
        f"[DEBUG] Custom Reducer: After _validate_and_filter_tool_message_pairs ({len(final_validated_messages)} messages):"
    )
    for i, msg in enumerate(final_validated_messages):
        msg_id = getattr(msg, "id", "NO_ID")
        print(f"  F[{i}] Type={type(msg).__name__}, ID={msg_id}")
    # --------------------------------------------

    final_messages = final_validated_messages

    logger.debug(
        f"Custom reducer produced {len(final_messages)} messages after filtering system messages and validating tools."
    )
    # --- DEBUG PRINT: Final return ---
    print(
        f"[DEBUG] Custom Reducer: FINISHED. Returning {len(final_messages)} messages."
    )
    # ----------------------------------
    return final_messages
