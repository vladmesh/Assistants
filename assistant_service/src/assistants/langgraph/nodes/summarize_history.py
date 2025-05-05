import json
import logging
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from assistants.langgraph.prompt_context_cache import PromptContextCache
from assistants.langgraph.state import AssistantState
from assistants.langgraph.utils.token_counter import count_tokens
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Configuration
SUMMARY_THRESHOLD_PERCENT = 0.6
MESSAGES_TO_KEEP_TAIL = 5
CONTEXT_SAFETY_MARGIN_RATIO = 0.9  # Use 90% of context limit as a safety buffer


def should_summarize(
    state: AssistantState,
    prompt_context_cache: PromptContextCache,
    system_prompt_template: str,
    max_tokens: int,
) -> Literal["summarize", "assistant"]:
    """
    Checks if the total token count (including the anticipated dynamic SystemMessage)
    exceeds the summarization threshold.
    Uses max_tokens for the context limit check.
    """
    messages = state.get("messages", [])
    context_limit = max_tokens
    log_extra = state.get("log_extra", {})

    if not messages or context_limit <= 0:
        logger.warning(
            f"[should_summarize] Skipping check: No messages ({len(messages)}) or context_limit <= 0 ({context_limit}).",
            extra=log_extra,
        )
        return "assistant"

    # --- Estimate Dynamic System Message Tokens ---
    # Use cached data directly, do not fetch here
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
    except Exception as e:
        logger.error(
            f"[should_summarize] Error formatting/counting temp system prompt: {e}. Assuming 0 tokens.",
            extra=log_extra,
        )
        system_prompt_tokens = 0
    # -----------------------------------------

    # --- Calculate Total Tokens ---
    history_tokens = count_tokens(messages)
    total_estimated_tokens = system_prompt_tokens + history_tokens
    # ----------------------------

    ratio = (total_estimated_tokens / context_limit) if context_limit else 0

    # Определяем порог на основе переданного размера окна
    # Используем процент от лимита, например, 60%
    threshold = SUMMARY_THRESHOLD_PERCENT

    decision = "summarize" if ratio >= threshold else "assistant"

    logger.info(
        f"[should_summarize] Check result: Tokens={total_estimated_tokens}, Limit={context_limit}, Ratio={ratio:.2f}, Threshold={threshold:.2f}, Decision='{decision}'",
        extra=log_extra,
    )

    return decision


async def _call_llm(
    llm: BaseChatModel, prompt: List[BaseMessage], limit: int, iteration: int
) -> Optional[str]:
    tokens = count_tokens(prompt)
    logger.warning(
        f"[_call_llm] Iter {iteration}: Prompt tokens = {tokens}, Limit = {limit}"
    )
    if tokens >= limit:
        logger.warning(f"[_call_llm] Iter {iteration}: tokens >= limit, skipping call.")
        return None
    logger.warning(f"[_call_llm] Iter {iteration}: Invoking LLM...")
    response = await llm.ainvoke(prompt)

    content = response.content if hasattr(response, "content") else str(response)
    content_len = len(content) if content is not None else 0
    logger.warning(
        f"[_call_llm] Iter {iteration}: Received response length = {content_len}"
    )
    return content


def _create_prompt(prev_summary: str, chunk_json: str) -> List[BaseMessage]:
    messages: List[BaseMessage] = []

    if prev_summary:
        messages.append(SystemMessage(content=f"Current summary: {prev_summary}"))
    text = (
        f"Основываясь на саммари и следующем списке сообщений, обнови саммари:\n```json\n{chunk_json}\n```"
        if prev_summary
        else f"Создай саммари из следующего списка сообщений:\n```json\n{chunk_json}\n```"
    )
    messages.append(HumanMessage(content=text))
    logger.warning(f"[_create_prompt] Built prompt with {len(messages)} messages.")
    return messages


def _make_json_chunk(messages: List[BaseMessage]) -> str:
    logger.warning(f"[_make_json_chunk] Serializing {len(messages)} messages to JSON.")
    data = []
    for msg in messages:
        content = getattr(msg, "content", "")
        if not content:
            logger.warning(
                f"[_make_json_chunk] Skipping empty message of type {type(msg).__name__}."
            )
            continue
        entry = {"type": type(msg).__name__.replace("Message", ""), "Content": content}
        name = getattr(msg, "name", None)
        if name:
            entry["Name"] = name
            logger.warning(
                f"[_make_json_chunk] Message has name '{name}', including it."
            )
        data.append(entry)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    logger.warning(f"[_make_json_chunk] Generated JSON chunk length = {len(json_str)}")
    return json_str


def _select_messages(
    messages: List[BaseMessage], tail_count: int
) -> Tuple[List[BaseMessage], List[int]]:
    """Selects head messages to summarize and their indices."""
    logger.warning(
        f"[_select_messages] Selecting messages with tail_count = {tail_count}."
    )
    # No longer need to find old summaries, reducer handles them.
    # Filter out any potential system messages just in case reducer missed something (unlikely)
    non_system_messages = [
        (i, m) for i, m in enumerate(messages) if not isinstance(m, SystemMessage)
    ]

    if len(non_system_messages) <= tail_count:
        logger.warning(
            "[_select_messages] Not enough non-system messages to summarize."
        )
        return [], []  # Return empty lists

    # Messages to summarize are all non-system messages except the tail
    head_part = non_system_messages[:-tail_count]
    head_msgs = [m for _, m in head_part]
    head_idxs = [i for i, _ in head_part]  # These are the indices to remove

    logger.warning(
        f"[_select_messages] Selected {len(head_msgs)} head messages for summary. Indices to remove: {head_idxs}"
    )
    # --- DEBUG ---
    if head_msgs and hasattr(head_msgs[0], "id"):
        logger.warning(
            f"[_select_messages] DEBUG: ID of the first message to be summarized/removed: {head_msgs[0].id}"
        )
    # -------------
    # Returns only head messages and indices to remove
    return head_msgs, head_idxs


async def summarize_history_node(
    state: AssistantState,
    summary_llm: BaseChatModel,
    rest_client: RestServiceClient,
    summarization_prompt: str,
) -> Dict[str, Any]:
    """
    Summarizes history, saves the summary via REST API, and returns RemoveMessage instructions.
    Uses the provided summarization_prompt.
    """
    logger.warning("[summarize_history_node] ENTERED (v2 - DB Save).")
    messages = state.get("messages", [])
    context_size = state.get("llm_context_size", 0)
    user_id_str = state.get("user_id")  # Get user_id from state
    assistant_id_str = state.get("log_extra", {}).get(
        "assistant_id"
    )  # Get assistant_id from log_extra
    log_extra = state.get("log_extra", {})  # Added for print

    # --- Input Validation ---
    if not messages or context_size <= 0:
        logger.warning(
            "Prerequisites not met (no messages or context size <= 0), skipping.",
            extra=log_extra,
        )
        return {"messages": []}

    if not user_id_str or not assistant_id_str:
        logger.error(
            "User ID or Assistant ID not found in state, cannot save summary.",
            extra=log_extra,
        )
        # Proceed with summarization but cannot save. Return empty message list?
        # Or raise? For now, just return empty to avoid breaking flow, but log error.
        return {"messages": []}

    user_id_int: Optional[int] = None
    try:
        user_id_int = int(user_id_str)
    except ValueError:
        logger.error(
            f"Invalid User ID format '{user_id_str}', cannot save summary.",
            extra=log_extra,
        )
        return {"messages": []}

    # --- Select messages to summarize ---
    head_msgs, head_idxs = _select_messages(messages, MESSAGES_TO_KEEP_TAIL)
    if not head_msgs:
        logger.warning(
            "No messages selected for summarization, exiting node.", extra=log_extra
        )
        return {"messages": []}
    # --- DEBUG: Log ID of first message to be removed ---
    if head_msgs and hasattr(head_msgs[0], "id"):
        logger.info(f"[Summarize Node] First message to remove ID: {head_msgs[0].id}")
    # -----------------------------------------------------

    # --- Prepare summary request ---
    prev_summary = state.get("current_summary", "")
    json_chunk = _make_json_chunk(head_msgs)
    prompt = _create_prompt_with_template(
        prev_summary, json_chunk, summarization_prompt
    )

    # --- Call LLM for summarization ---
    new_summary: Optional[str] = None
    try:
        logger.info(
            f"Invoking summary LLM. Prompt length: {len(str(prompt))}", extra=log_extra
        )
        # Simple call, no iterative reduction here for now
        # Consider context limit if summary LLM has one
        response = await summary_llm.ainvoke(prompt)
        new_summary = (
            response.content if hasattr(response, "content") else str(response)
        )
        logger.info("Summary LLM call successful.", extra=log_extra)
    except Exception as e:
        logger.exception("Error calling summary LLM", exc_info=True, extra=log_extra)
        # Decide how to proceed: use old summary? skip update?
        # For now, we'll proceed without updating the summary if LLM fails
        new_summary = None  # Ensure summary is None if failed

    # --- Save Summary via REST ---
    remove_instructions: List[BaseMessage] = []
    if new_summary:
        logger.info(
            f"Attempting to save new summary (length {len(new_summary)}) via REST...",
            extra=log_extra,
        )
        try:
            # Make sure assistant_id_str is a valid UUID string
            assistant_uuid = str(uuid.UUID(assistant_id_str))
            # Save using user_id_int and assistant_uuid
            await rest_client.save_summary(user_id_int, assistant_uuid, new_summary)
            logger.info(
                f"Successfully saved summary for user {user_id_int}, assistant {assistant_uuid}",
                extra=log_extra,
            )

            # Only generate RemoveMessages if summary was successfully saved
            remove_instructions = [
                RemoveMessage(id=messages[idx].id)
                for idx in head_idxs
                if hasattr(messages[idx], "id") and messages[idx].id
            ]
            logger.info(
                f"Generated {len(remove_instructions)} RemoveMessage instructions.",
                extra=log_extra,
            )

        except ValueError as e:
            logger.error(
                f"Invalid Assistant ID format '{assistant_id_str}': {e}. Cannot save summary.",
                extra=log_extra,
            )
            # Don't generate remove instructions if we couldn't save
        except Exception as e:
            logger.exception(
                "Error saving summary via REST API", exc_info=True, extra=log_extra
            )
            # Don't generate remove instructions if we couldn't save
    else:
        logger.warning(
            "No new summary generated or LLM call failed, skipping REST save and message removal.",
            extra=log_extra,
        )

    # Return RemoveMessage instructions ONLY if summary was successfully generated AND saved
    return {"messages": remove_instructions}


# Helper function to create prompt using the template
def _create_prompt_with_template(
    prev_summary: str, chunk_json: str, template: str
) -> List[BaseMessage]:
    """Creates the summarization prompt using a template."""
    try:
        content = template.format(
            previous_summary=prev_summary, message_chunk_json=chunk_json
        )
        logger.info(
            f"Generated summarization prompt using template. Length: {len(content)}"
        )
        return [HumanMessage(content=content)]
    except KeyError as e:
        logger.error(
            f"Error formatting summarization prompt template: Missing key {e}",
            exc_info=True,
        )
        # Fallback to a basic prompt if template fails
        logger.warning(
            "Falling back to basic summarization prompt due to template error."
        )
        fallback_content = (
            f"Current summary: {prev_summary}\n\n"
            if prev_summary
            else "" f"Summarize the following messages:\n```json\n{chunk_json}\n```"
        )
        return [HumanMessage(content=fallback_content)]
    except Exception as e:
        logger.exception(
            "Unexpected error creating prompt from template.", exc_info=True
        )
        logger.warning(
            "Falling back to basic summarization prompt due to unexpected error."
        )
        fallback_content = (
            f"Current summary: {prev_summary}\n\n"
            if prev_summary
            else "" f"Summarize the following messages:\n```json\n{chunk_json}\n```"
        )
        return [HumanMessage(content=fallback_content)]


# Keep other helper functions like _make_json_chunk, _select_messages, _call_llm if they are still used/needed.
# Remove _create_prompt if replaced by _create_prompt_with_template
# Ensure all necessary imports are present.

# Placeholder for removed _create_prompt to avoid breaking changes if called elsewhere unexpectedly
# def _create_prompt(prev_summary: str, chunk_json: str) -> List[BaseMessage]:
#     logger.error("_create_prompt is deprecated. Use _create_prompt_with_template.")
#     raise NotImplementedError("_create_prompt is deprecated.")
