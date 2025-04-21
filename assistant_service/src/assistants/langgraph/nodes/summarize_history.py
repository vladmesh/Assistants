import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from assistants.langgraph.constants import HISTORY_SUMMARY_NAME
from assistants.langgraph.state import AssistantState
from assistants.langgraph.utils.token_counter import count_tokens
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Configuration
SUMMARY_THRESHOLD_PERCENT = 0.6
MESSAGES_TO_KEEP_TAIL = 5
CONTEXT_SAFETY_MARGIN_RATIO = 0.9  # Use 90% of context limit as a safety buffer


def should_summarize(state: AssistantState) -> Literal["summarize", "assistant"]:
    print(
        "##################################################################################################################################################################################"
    )
    print(
        "---------------------------------------should_summarize-----------------------------------------------------------------------------------------------------------------"
    )
    print(
        "##################################################################################################################################################################################"
    )
    messages = state.get("messages", [])
    current_tokens = count_tokens(messages)
    context_limit = state.get("llm_context_size", 8192)
    ratio = (current_tokens / context_limit) if context_limit else 0
    # Add more detailed logging for debugging
    logger.warning(
        f"[should_summarize] Check state: context_limit={context_limit}, tokens={current_tokens}, ratio={ratio:.2f}"
    )
    decision = "summarize" if ratio >= SUMMARY_THRESHOLD_PERCENT else "assistant"
    logger.warning(f"[should_summarize] Decision: {decision}")
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
    await asyncio.sleep(10)
    return content


def _create_prompt(prev_summary: str, chunk_json: str) -> List[BaseMessage]:
    messages: List[BaseMessage] = []
    if prev_summary:
        messages.append(SystemMessage(content=f"Previous summary: {prev_summary}"))
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
) -> Tuple[List[BaseMessage], List[int], str]:
    logger.warning(
        f"[_select_messages] Selecting messages to summarize with tail_count = {tail_count}."
    )
    summary_idxs: List[int] = []
    prev_summary = ""
    for i, msg in enumerate(messages):
        if isinstance(msg, SystemMessage) and msg.name == HISTORY_SUMMARY_NAME:
            summary_idxs.append(i)
            prev_summary = msg.content or prev_summary
            logger.warning(f"[_select_messages] Found previous summary at index {i}.")
    non_summary = [(i, m) for i, m in enumerate(messages) if i not in summary_idxs]
    if len(non_summary) <= tail_count:
        logger.warning("[_select_messages] Not enough messages to summarize, skipping.")
        return [], summary_idxs, prev_summary
    head_part = non_summary[:-tail_count]
    head_msgs = [m for _, m in head_part]
    head_idxs = [i for i, _ in head_part]
    remove_idxs = sorted(summary_idxs + head_idxs)
    logger.warning(
        f"[_select_messages] Selected {len(head_msgs)} head messages, will remove {len(remove_idxs)} msgs."
    )
    return head_msgs, remove_idxs, prev_summary


async def summarize_history_node(
    state: AssistantState, summary_llm: BaseChatModel
) -> Dict[str, Any]:
    logger.warning("[summarize_history_node] ENTERED.")  # Log entry
    messages = state.get("messages", [])
    context_size = state.get("llm_context_size", 0)
    logger.warning(
        f"[summarize_history_node] Initial messages count = {len(messages)}, context_size = {context_size}."
    )
    if not messages or context_size <= 0:
        logger.warning(
            "[summarize_history_node] Prerequisites not met (no messages or context size <= 0), skipping."
        )
        return {"messages": []}  # Return empty list, not None

    head_msgs, remove_idxs, prev_summary = _select_messages(
        messages, MESSAGES_TO_KEEP_TAIL
    )

    # Create delete instructions for ALL messages identified for removal (old summaries + all head messages)
    # These will be removed regardless of whether they made it into the new summary.
    initial_deletes = [
        RemoveMessage(id=messages[i].id)
        for i in remove_idxs
        if hasattr(messages[i], "id")
    ]
    logger.warning(
        f"[summarize_history_node] Created {len(initial_deletes)} initial delete instructions for indices: {remove_idxs}"
    )
    # ------------------------------------------------------------------------

    if not head_msgs:
        # If no messages to summarize, just return the deletes (likely only old summaries)
        logger.warning(
            f"[summarize_history_node] No head msgs, returning initial deletes."
        )
        return {"messages": initial_deletes}

    # --- Start of New Logic (Step 4) ---
    effective_context_limit = int(context_size * CONTEXT_SAFETY_MARGIN_RATIO)
    logger.warning(
        f"[summarize_history_node] Effective context limit for summary prompt: {effective_context_limit}"
    )

    new_summary = prev_summary
    chunk: List[BaseMessage] = []
    iteration = 0
    last_valid_prompt: Optional[List[BaseMessage]] = None
    processed_head_ids_in_summary = (
        set()
    )  # Track IDs successfully included in a summary call

    for msg in head_msgs:
        if not hasattr(msg, "id"):
            logger.warning(
                f"[summarize_history_node] Skipping message without ID: {type(msg).__name__}"
            )
            continue

        potential_chunk = chunk + [msg]
        potential_chunk_json = _make_json_chunk(potential_chunk)
        potential_prompt = _create_prompt(new_summary, potential_chunk_json)
        prompt_tokens = count_tokens(potential_prompt)

        if prompt_tokens <= effective_context_limit:
            # Message fits, add to chunk and store the valid prompt
            chunk = potential_chunk
            last_valid_prompt = potential_prompt
            logger.warning(
                f"[summarize_history_node] Message ID {msg.id} fits ({prompt_tokens} tokens). Chunk size: {len(chunk)}."
            )
        else:
            # Message doesn't fit. Time to process the previous valid chunk (if any).
            logger.warning(
                f"[summarize_history_node] Message ID {msg.id} does NOT fit ({prompt_tokens} > {effective_context_limit}). Processing previous chunk (size {len(chunk)})."
            )
            if last_valid_prompt:
                # Process the last valid chunk
                logger.warning(
                    f"[summarize_history_node] Calling LLM for last valid prompt ({count_tokens(last_valid_prompt)} tokens)."
                )
                response = await _call_llm(
                    summary_llm, last_valid_prompt, effective_context_limit, 0
                )
                if response:
                    new_summary = response
                    processed_ids = {m.id for m in chunk if hasattr(m, "id")}
                    processed_head_ids_in_summary.update(processed_ids)
                    logger.warning(
                        f"[summarize_history_node] LLM call successful. Updated summary (length {len(new_summary)}). Added IDs to processed: {processed_ids}"
                    )
                else:
                    logger.warning(
                        "[summarize_history_node] LLM call failed or returned empty. Summary not updated for this chunk."
                    )
                    # Keep old summary, do not mark IDs as processed for this failed chunk.

                # Start a new chunk with the current message
                chunk = [msg]
                current_chunk_json = _make_json_chunk(chunk)
                current_prompt = _create_prompt(new_summary, current_chunk_json)
                current_tokens = count_tokens(current_prompt)
                if current_tokens <= effective_context_limit:
                    last_valid_prompt = current_prompt
                    logger.warning(
                        f"[summarize_history_node] Started new chunk with message ID {msg.id} ({current_tokens} tokens)."
                    )
                else:
                    # Even the single message chunk is too large
                    logger.warning(
                        f"[summarize_history_node] Single message ID {msg.id} is too large ({current_tokens} > {effective_context_limit}) with current summary. Skipping message."
                    )
                    chunk = []
                    last_valid_prompt = None
            else:
                # No last_valid_prompt means even the first message didn't fit
                logger.warning(
                    f"[summarize_history_node] First message ID {msg.id} in chunk too large ({prompt_tokens} > {effective_context_limit}). Skipping message."
                )
                chunk = []  # Reset chunk as this message is skipped
                last_valid_prompt = None

    # After the loop, process the final chunk if it exists and was valid
    if last_valid_prompt:
        logger.warning(
            f"[summarize_history_node] Processing final chunk (size {len(chunk)}) after loop."
        )
        response = await _call_llm(
            summary_llm, last_valid_prompt, effective_context_limit, 0
        )
        if response:
            new_summary = response
            processed_ids = {m.id for m in chunk if hasattr(m, "id")}
            processed_head_ids_in_summary.update(processed_ids)
            logger.warning(
                f"[summarize_history_node] Final LLM call successful. Updated summary (length {len(new_summary)}). Added IDs to processed: {processed_ids}"
            )
        else:
            logger.warning(
                "[summarize_history_node] Final LLM call failed or returned empty. Summary not updated for the last chunk."
            )

    logger.warning(
        f"[summarize_history_node] Total messages successfully processed into summary: {len(processed_head_ids_in_summary)}"
    )
    # --- End of New Logic (Step 4) ---

    # Combine initial deletes (old summaries + heads) with the new summary message
    summary_msg = SystemMessage(content=new_summary, name=HISTORY_SUMMARY_NAME)
    updates = initial_deletes + [summary_msg]
    try:
        remove_msg_ids = [
            rm.id for rm in initial_deletes if isinstance(rm, RemoveMessage)
        ]
        logger.warning(
            f"[summarize_history_node] COMPLETED. Returning RemoveMessage IDs: {remove_msg_ids}, and 1 SystemMessage."
        )
    except Exception as e:
        logger.error(f"[summarize_history_node] Error formatting log message: {e}")
        logger.warning(
            f"[summarize_history_node] COMPLETED. Returning updates (raw): {updates}"
        )
    return {"messages": updates, "last_summary_ts": datetime.utcnow()}
