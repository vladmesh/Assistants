import json
import logging
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

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

from shared_models.api_schemas.user_summary import UserSummaryCreateUpdate

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Configuration
SUMMARY_THRESHOLD_PERCENT = 0.6
MESSAGES_TO_KEEP_TAIL = 5
CONTEXT_SAFETY_MARGIN_RATIO = 0.9  # Use 90% of context limit as a safety buffer


def should_summarize(
    state: AssistantState,
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
    cached_summary = state["current_summary_content"]
    cached_facts = state["user_facts"]

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


async def _call_llm(llm: BaseChatModel, prompt: str) -> Optional[str]:
    response = await llm.ainvoke(prompt)

    content = response.content if hasattr(response, "content") else str(response)
    return content


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
) -> Tuple[List[BaseMessage], List[int], List[int]]:
    """
    Selects head messages to summarize and their indices.
    Also collects message IDs for messages that will be summarized
    """
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
        return [], [], []  # Return empty lists

    # Messages to summarize are all non-system messages except the tail
    head_part = non_system_messages[:-tail_count]
    head_msgs = [m for _, m in head_part]

    # NEW: Collect message IDs for messages that will be summarized
    message_ids = []
    for _, msg in head_part:
        message_ids.append(msg.id)

    logger.warning(
        f"[_select_messages] Selected {len(head_msgs)} head messages for summary."
    )
    logger.warning(
        f"[_select_messages] Collected {len(message_ids)} message IDs for summarized messages."
    )

    # Returns head messages, indices to remove, and message IDs
    return head_msgs, message_ids


async def summarize_history_node(
    state: AssistantState,
    summary_llm: BaseChatModel,
    rest_client: RestServiceClient,
    summarization_prompt: str,
) -> Dict[str, Any]:
    """
    Summarizes history, saves the summary via REST API, and returns updated state.
    Uses the provided summarization_prompt.
    """
    logger.warning("[summarize_history_node] ENTERED (v3 - DB Save with IDs).")
    messages = state.get("messages", [])
    context_size = state.get("llm_context_size", 0)
    user_id_str = state.get("user_id")  # Get user_id from state
    assistant_id_str = state.get("assistant_id")  # Get assistant_id from state
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
    head_msgs, message_ids = _select_messages(messages, MESSAGES_TO_KEEP_TAIL)
    if not head_msgs:
        logger.warning(
            "No messages selected for summarization, exiting node.", extra=log_extra
        )
        return {"messages": []}

    # --- Get existing summary if any ---
    prev_summary_text = state["current_summary_content"]
    # --- Create chunk and prompt ---
    chunk_json = _make_json_chunk(head_msgs)
    if not chunk_json:
        logger.warning("JSON chunk is empty, skipping summarization.", extra=log_extra)
        return {"messages": []}

    logger.info("Using provided summarization prompt template.", extra=log_extra)
    prompt = _create_prompt_with_template(
        prev_summary_text, chunk_json, summarization_prompt
    )

    # --- Call LLM for summarization ---
    # Attempt up to 3 iterations
    max_iterations = 3
    iteration = 1
    summary_text = None
    while iteration <= max_iterations and not summary_text:
        logger.info(f"Attempting summarization iteration {iteration}.", extra=log_extra)
        summary_text = await _call_llm(
            summary_llm,
            prompt,
        )
    if not summary_text:
        logger.error("Failed to generate summary.", extra=log_extra)
        return {"messages": []}

    # --- Save summary to database ---
    # Find last message in the summarized set to track coverage
    last_message_id = max(message_ids) if message_ids else None

    token_count = count_tokens([SystemMessage(content=summary_text)])

    # Преобразуем assistant_id в строку, чтобы избежать ошибки сериализации UUID
    assistant_id_str_safe = str(assistant_id_str)

    summary_data = UserSummaryCreateUpdate(
        user_id=user_id_int,
        assistant_id=assistant_id_str_safe,
        summary_text=summary_text,
        last_message_id_covered=last_message_id,
        token_count=token_count,
    )

    try:
        await rest_client.create_user_summary(summary_data)
        logger.info(
            f"Successfully saved summary (last_message_id={last_message_id}, tokens={token_count}).",
            extra=log_extra,
        )
    except Exception as e:
        logger.error(f"Error saving summary: {e}", extra=log_extra)
        # Continue since we still want to update the state even if save fails

    # --- Update state ---
    remove_instructions = [RemoveMessage(msg_id) for msg_id in message_ids]

    logger.warning(
        f"[summarize_history_node] Created {len(remove_instructions)} RemoveMessage instructions using indices"
    )

    return {
        "messages": remove_instructions,
        "current_summary_content": summary_text,
        "newly_summarized_message_ids": message_ids,
    }


def _create_prompt_with_template(
    prev_summary: str, chunk_json: str, template: str
) -> BaseMessage:
    """Creates a prompt using a provided template string."""
    try:
        # Format the template with json chunk
        formatted_content = template.format(
            json=chunk_json, current_summary=prev_summary or "No existing summary."
        )
        return formatted_content
    except Exception as e:
        logger.error(f"Error creating prompt with template: {e}")
        raise e
