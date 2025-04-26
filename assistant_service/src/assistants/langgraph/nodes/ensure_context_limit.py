import logging
from typing import Any, Dict, List

from assistants.langgraph.prompt_context_cache import PromptContextCache
from assistants.langgraph.state import AssistantState
from assistants.langgraph.utils.token_counter import count_tokens
from langchain_core.messages import BaseMessage, RemoveMessage, SystemMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Конфигурация
TRIM_THRESHOLD_PERCENT = 1.0  # допустимая пропорция от лимита
MIN_CONTENT_LEN = 50  # минимальная длина контента
CHUNK_REDUCTION_FACTOR = 0.10  # доля отрезаемая за итерацию


def _create_truncated_message(orig: BaseMessage, content: str) -> BaseMessage:
    kwargs = {"content": content}
    if hasattr(orig, "id"):
        kwargs["id"] = orig.id
    if hasattr(orig, "name"):
        kwargs["name"] = orig.name
    if hasattr(orig, "tool_call_id"):
        kwargs["tool_call_id"] = orig.tool_call_id
    logger.info(f"[truncate] Recreating {type(orig).__name__} id={kwargs.get('id')}")
    return type(orig)(**kwargs)


def ensure_context_limit_node(
    state: AssistantState,
    prompt_context_cache: PromptContextCache,
    system_prompt_template: str,
) -> Dict[str, Any]:
    """
    Ensures the message history fits within the token limit, considering the
    space needed for the dynamically generated SystemMessage.

    1. Calculates the available token limit for history.
    2. If history exceeds the limit, removes oldest messages first.
    3. If removing isn't enough, truncates the now-oldest remaining message.
    4. Returns RemoveMessage instructions and potentially one updated (truncated) message.
    """
    messages = state.get("messages", [])
    context_limit = state.get("llm_context_size", 0)
    log_extra = state.get("log_extra", {})
    safety_margin = 0.95  # Use 95% - slightly less aggressive than summary check
    effective_limit = int(context_limit * safety_margin) if context_limit > 0 else 0

    incoming_types = [type(m).__name__ for m in messages]
    logger.info(
        f"[ensure_limit] ENTERED (v2 - using cache). Msgs: {len(messages)}, Types: {incoming_types}, "
        f"Total_Limit: {context_limit}, Effective_Limit: {effective_limit}"
    )

    if not messages or effective_limit <= 0:
        logger.warning("[ensure_limit] No messages or invalid limit, skipping.")
        return {"messages": []}

    # --- Calculate System Prompt Tokens --- #
    # Use cached data directly
    cached_summary = prompt_context_cache.summary
    cached_facts = prompt_context_cache.facts
    facts_str = (
        "\n".join(f"- {fact}" for fact in cached_facts)
        if cached_facts
        else "Нет известных фактов."
    )
    summary_str = (
        cached_summary
        if cached_summary
        else "Нет предыдущей истории диалога (саммари)."
    )

    try:
        formatted_prompt_content = system_prompt_template.format(
            summary_previous=summary_str, user_facts=facts_str
        )
        temp_system_message = SystemMessage(content=formatted_prompt_content)
        system_prompt_tokens = count_tokens([temp_system_message])
        logger.info(
            f"[ensure_limit] Estimated system prompt tokens: {system_prompt_tokens}"
        )
    except Exception as e:
        logger.error(
            f"[ensure_limit] Error formatting/counting temp system prompt: {e}. Assuming 0.",
            extra=log_extra,
        )
        system_prompt_tokens = 0
    # ----------------------------------- #

    # --- Calculate Available History Limit --- #
    history_token_limit = effective_limit - system_prompt_tokens
    if history_token_limit <= 0:
        logger.error(
            f"[ensure_limit] Effective limit {effective_limit} is less than or equal to system prompt tokens {system_prompt_tokens}. Cannot fit history.",
            extra=log_extra,
        )
        # Remove ALL history? Or raise error? Let's remove all for now.
        remove_all_ids = [
            m.id for m in messages if hasattr(m, "id") and m.id is not None
        ]
        logger.warning(
            f"[ensure_limit] Removing all {len(remove_all_ids)} history messages.",
            extra=log_extra,
        )
        return {"messages": [RemoveMessage(id=rid) for rid in remove_all_ids]}

    target_tokens = int(history_token_limit * TRIM_THRESHOLD_PERCENT)
    logger.info(
        f"[ensure_limit] Target tokens for history: {target_tokens} (after reserving {system_prompt_tokens} for system prompt)"
    )
    # ------------------------------------- #

    # --- Check Current History Tokens --- #
    # We only count tokens of messages currently in the state (history)
    current_history_tokens = count_tokens(messages)
    logger.info(
        f"[ensure_limit] Current history tokens: {current_history_tokens} > Target history tokens: {target_tokens}?"
    )

    if current_history_tokens <= target_tokens:
        logger.info(
            "[ensure_limit] History token limit not exceeded, no action needed."
        )
        return {"messages": []}  # Return empty list, indicating no changes
    # --------------------------------- #

    # --- Limit Exceeded: Apply Truncation/Removal --- #
    logger.warning(
        f"[ensure_limit] History limit exceeded ({current_history_tokens} > {target_tokens}). Applying removal/truncation."
    )
    working = messages.copy()  # Work on a copy
    removed_ids = set()
    updates: List[Any] = []

    # 1. Remove oldest messages until limit is met
    current_tokens_in_loop = count_tokens(working)  # Use pre-calculated count
    while (
        current_tokens_in_loop > target_tokens and working
    ):  # Check if list is not empty
        msg_to_remove = working.pop(0)  # Remove from the start (oldest)
        msg_id = getattr(msg_to_remove, "id", None)
        if msg_id:
            removed_ids.add(msg_id)
            logger.info(f"[ensure_limit] Removing oldest message ID {msg_id}")
        else:
            logger.warning("[ensure_limit] Removed oldest message but it had no ID.")
        # Recalculate tokens *after* removal
        current_tokens_in_loop = count_tokens(working)
        logger.info(
            f"[ensure_limit] After removing oldest, remaining tokens: {current_tokens_in_loop}"
        )

    # Add RemoveMessage instructions for all removed IDs
    updates.extend([RemoveMessage(id=rid) for rid in removed_ids])
    logger.info(f"[ensure_limit] Added {len(removed_ids)} RemoveMessage instructions.")

    # 2. If still over limit after removing messages, truncate the oldest *remaining* message
    current_tokens_after_removal = (
        current_tokens_in_loop  # Use the count from the end of the previous loop
    )
    if current_tokens_after_removal > target_tokens and working:
        logger.warning(
            f"[ensure_limit] Still over limit ({current_tokens_after_removal} > {target_tokens}) after removal. Truncating oldest remaining message."
        )
        message_to_truncate = working[0]  # Oldest remaining message
        original_content = getattr(message_to_truncate, "content", "") or ""
        content_to_truncate = original_content
        truncated_during_loop = False

        # Use count_tokens on the *whole* working list inside the loop
        current_tokens_in_trunc_loop = (
            current_tokens_after_removal  # Start with the known count
        )

        while (
            len(content_to_truncate) > MIN_CONTENT_LEN
            and current_tokens_in_trunc_loop > target_tokens
        ):
            cut = max(int(len(content_to_truncate) * CHUNK_REDUCTION_FACTOR), 100)
            content_to_truncate = content_to_truncate[:-cut]
            # Create based on the original message object
            truncated_msg_obj = _create_truncated_message(
                message_to_truncate, content_to_truncate + "..."
            )
            working[0] = truncated_msg_obj  # Update the working list
            current_tokens_in_trunc_loop = count_tokens(working)  # Recalculate
            logger.info(
                f"[ensure_limit] Truncating oldest msg id={getattr(message_to_truncate, 'id', 'N/A')} "
                f"to len={len(content_to_truncate)}, remaining tokens={current_tokens_in_trunc_loop}"
            )
            truncated_during_loop = True
            # Check if we fit *after* this truncation step
            if current_tokens_in_trunc_loop <= target_tokens:
                logger.info(
                    "[ensure_limit] Target tokens reached during truncation loop."
                )
                break  # Exit truncation loop

        # Add the truncated message to updates *only if it changed*
        if truncated_during_loop and working[0].content != original_content:
            logger.info(
                f"[ensure_limit] Appending truncated oldest message id={getattr(working[0], 'id', 'N/A')} to updates."
            )
            # Check if a RemoveMessage for this ID already exists (shouldn't, as it wasn't removed)
            if getattr(working[0], "id", None) not in removed_ids:
                updates.append(working[0])  # Append the modified message object
            else:
                logger.warning(
                    f"[ensure_limit] Tried to append truncated message {getattr(working[0], 'id', 'N/A')} but it was already marked for removal?"
                )
        else:
            logger.info(
                "[ensure_limit] Truncated oldest message not appended (not truncated or content unchanged)."
            )

    # --- Final Check and Return --- #
    final_tokens_in_working = count_tokens(
        working
    )  # Recalculate final tokens in potentially modified list
    if final_tokens_in_working > target_tokens:
        logger.error(
            f"[ensure_limit] FAILED to bring history tokens ({final_tokens_in_working}) within target ({target_tokens}) after all steps!",
            extra=log_extra,
        )
        # Return the updates we have, but log error. Maybe raise?

    logger.info(
        f"[ensure_limit] COMPLETED. Returning {len(updates)} update instructions.",
        extra=log_extra,
    )
    return {"messages": updates}
