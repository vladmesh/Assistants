import asyncio
import json
import logging
import uuid
from datetime import datetime
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
) -> Literal["summarize", "assistant"]:
    """
    Checks if the total token count (including the anticipated dynamic SystemMessage)
    exceeds the summarization threshold.
    """
    messages = state.get("messages", [])
    context_limit = state.get("llm_context_size", 8192)
    log_extra = state.get("log_extra", {})

    if not messages or context_limit <= 0:
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

    decision = "summarize" if ratio >= SUMMARY_THRESHOLD_PERCENT else "assistant"
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
        logger.warning("[_create_prompt] Including previous summary in prompt.")
    else:
        logger.warning("[_create_prompt] No previous summary, initial summary prompt.")
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
    state: AssistantState, summary_llm: BaseChatModel, rest_client: RestServiceClient
) -> Dict[str, Any]:
    """
    Summarizes history, saves the summary via REST API, and returns RemoveMessage instructions.
    """
    logger.warning("[summarize_history_node] ENTERED (v2 - DB Save).")
    messages = state.get("messages", [])
    context_size = state.get("llm_context_size", 0)
    user_id_str = state.get("user_id")  # Get user_id from state
    assistant_id_str = state.get("log_extra", {}).get(
        "assistant_id"
    )  # Get assistant_id from log_extra

    # --- Input Validation ---
    if not messages or context_size <= 0:
        logger.warning(
            "Prerequisites not met (no messages or context size <= 0), skipping."
        )
        return {"messages": []}

    if not user_id_str or not assistant_id_str:
        logger.error("Missing user_id or assistant_id in state, cannot save summary.")
        # Decide how to proceed: skip summarization or raise error? Let's skip.
        # We still need to return potential deletes if selection happened.
        return {"messages": []}  # Or potentially return deletes if needed later

    try:
        user_id_int = int(user_id_str)
        assistant_id_uuid = uuid.UUID(assistant_id_str)
    except (ValueError, TypeError) as e:
        logger.error(
            f"Invalid user_id or assistant_id format: {e}. Cannot save summary."
        )
        return {"messages": []}  # Skip

    log_extra = {"user_id": user_id_str, "assistant_id": assistant_id_str}
    # ----------------------

    logger.warning(
        f"Initial messages count = {len(messages)}, context_size = {context_size}.",
        extra=log_extra,
    )

    # Select messages to summarize (returns only head messages and indices to remove)
    head_msgs, remove_idxs = _select_messages(messages, MESSAGES_TO_KEEP_TAIL)

    # Create delete instructions for ALL head messages identified for removal.
    initial_deletes = [
        RemoveMessage(id=messages[i].id)
        for i in remove_idxs
        if hasattr(messages[i], "id") and messages[i].id is not None  # Ensure ID exists
    ]
    logger.warning(
        f"Created {len(initial_deletes)} delete instructions for head indices: {remove_idxs}",
        extra=log_extra,
    )

    if not head_msgs:
        # If no messages selected to summarize, just return the deletes (which would be empty).
        logger.warning(
            f"No head msgs to summarize, returning {len(initial_deletes)} deletes.",
            extra=log_extra,
        )
        return {"messages": initial_deletes}

    # --- Get Previous Summary (for prompt generation only) ---
    prev_summary: Optional[str] = None
    try:
        summary_data = await rest_client.get_user_summary(
            user_id=user_id_int, secretary_id=assistant_id_uuid
        )
        if summary_data and hasattr(summary_data, "summary_text"):
            prev_summary = summary_data.summary_text
            logger.info("Retrieved previous summary for context.", extra=log_extra)
        else:
            logger.info("No previous summary found via REST.", extra=log_extra)
    except Exception as e:
        logger.error(
            f"Failed to retrieve previous summary: {e}", exc_info=True, extra=log_extra
        )
        # Continue without previous summary if fetch fails

    # --- Summarization Loop (largely same as before) ---
    effective_context_limit = int(context_size * CONTEXT_SAFETY_MARGIN_RATIO)
    logger.warning(
        f"Effective context limit for summary prompt: {effective_context_limit}",
        extra=log_extra,
    )

    # Initialize new_summary with the previous one (or None)
    new_summary = prev_summary if prev_summary is not None else ""
    chunk: List[BaseMessage] = []
    iteration = 0
    last_valid_prompt: Optional[List[BaseMessage]] = None
    # No need to track processed IDs here, we just save the final summary

    for msg in head_msgs:
        if not hasattr(msg, "id"):
            logger.warning(f"Skipping message without ID: {type(msg).__name__}")
            continue
        iteration += 1

        potential_chunk = chunk + [msg]
        potential_chunk_json = _make_json_chunk(potential_chunk)
        # Use the potentially updated 'new_summary' from the previous iteration for the prompt
        potential_prompt = _create_prompt(new_summary, potential_chunk_json)
        prompt_tokens = count_tokens(potential_prompt)

        if prompt_tokens <= effective_context_limit:
            chunk = potential_chunk
            last_valid_prompt = potential_prompt
            logger.warning(
                f"Message ID {msg.id} fits ({prompt_tokens} tokens). Chunk size: {len(chunk)}.",
                extra=log_extra,
            )
        else:
            logger.warning(
                f"Message ID {msg.id} does NOT fit ({prompt_tokens} > {effective_context_limit}). Processing previous chunk (size {len(chunk)}).",
                extra=log_extra,
            )
            if last_valid_prompt:
                logger.warning(
                    f"Calling LLM for last valid prompt ({count_tokens(last_valid_prompt)} tokens).",
                    extra=log_extra,
                )
                response = await _call_llm(
                    summary_llm, last_valid_prompt, effective_context_limit, 0
                )
                if response:
                    new_summary = (
                        response  # Update summary for the next prompt generation
                    )
                    logger.warning(
                        f"LLM call successful. Updated intermediate summary (length {len(new_summary)}).",
                        extra=log_extra,
                    )
                else:
                    logger.warning(
                        "LLM call failed or returned empty. Summary not updated for this chunk.",
                        extra=log_extra,
                    )

                # Start new chunk with the current message
                chunk = [msg]
                current_chunk_json = _make_json_chunk(chunk)
                current_prompt = _create_prompt(
                    new_summary, current_chunk_json
                )  # Use latest summary
                current_tokens = count_tokens(current_prompt)
                if current_tokens <= effective_context_limit:
                    last_valid_prompt = current_prompt
                    logger.warning(
                        f"Started new chunk with message ID {msg.id} ({current_tokens} tokens).",
                        extra=log_extra,
                    )
                else:
                    last_valid_prompt = None  # Even single message doesn't fit
                    logger.warning(
                        f"Single message ID {msg.id} ({current_tokens} tokens) exceeds limit. Cannot process.",
                        extra=log_extra,
                    )
            else:
                # No valid prompt to process before this message
                logger.warning(
                    f"Message ID {msg.id} exceeds limit, and no previous chunk to process.",
                    extra=log_extra,
                )
                chunk = []  # Reset chunk
                last_valid_prompt = None

    # --- Process the final remaining chunk ---
    if last_valid_prompt:
        logger.warning(
            f"Processing final chunk (size {len(chunk)}, {count_tokens(last_valid_prompt)} tokens).",
            extra=log_extra,
        )
        response = await _call_llm(
            summary_llm, last_valid_prompt, effective_context_limit, 0
        )
        if response:
            new_summary = response  # Final summary content
            logger.warning(
                f"LLM call for final chunk successful. Final summary length: {len(new_summary)}.",
                extra=log_extra,
            )
        else:
            logger.warning(
                "LLM call for final chunk failed. Summary might be incomplete.",
                extra=log_extra,
            )
            # Keep the summary from the previous successful chunk (stored in new_summary)

    # --- Save the final summary via REST API --- #
    if (
        new_summary and new_summary != prev_summary
    ):  # Only save if there's a new/updated summary
        logger.info(
            f"Attempting to save summary (length {len(new_summary)}) via REST...",
            extra=log_extra,
        )
        try:
            await rest_client.create_or_update_user_summary(
                user_id=user_id_int,
                secretary_id=assistant_id_uuid,
                summary_text=new_summary,
            )
            logger.info("Successfully saved summary via REST.", extra=log_extra)
            # We rely on the assistant instance polling via needs_summary_refresh flag.

        except Exception as e:
            logger.error(
                f"Failed to save summary via REST: {e}", exc_info=True, extra=log_extra
            )
            # Even if save fails, we still need to return the deletes
    elif not new_summary:
        logger.warning("No new summary generated.", extra=log_extra)
    else:  # new_summary == prev_summary
        logger.info(
            "Generated summary is identical to the previous one, skipping save.",
            extra=log_extra,
        )

    # --- Return only the messages to be deleted --- #
    # DO NOT return the SystemMessage with the summary anymore.
    logger.warning(
        f"Summarization node finished. Returning {len(initial_deletes)} RemoveMessage instructions.",
        extra=log_extra,
    )
    return {"messages": initial_deletes}
