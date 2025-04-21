import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from assistants.langgraph.constants import HISTORY_SUMMARY_NAME
from assistants.langgraph.state import AssistantState
from assistants.langgraph.utils.token_counter import count_tokens
from langchain_core.messages import BaseMessage, RemoveMessage, SystemMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Конфигурация
TRIM_THRESHOLD_PERCENT = 0.90  # допустимая пропорция от лимита
MIN_CONTENT_LEN = 50  # минимальная длина контента
CHUNK_REDUCTION_FACTOR = (
    0.10  # доля отрезаемая за итерацию   # пауза после каждого усечения
)


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


async def ensure_context_limit_node(state: AssistantState) -> Dict[str, Any]:
    """
    1) Удаляем старые сообщения по RemoveMessage
    2) Усечённые версии summary + last message по ID
    """
    messages = state.get("messages", [])
    context_limit = state.get("llm_context_size", 0)
    safety_margin = 0.9  # Use 90% of limit
    effective_limit = int(context_limit * safety_margin) if context_limit > 0 else 0

    # Log entry
    incoming_types = [type(m).__name__ for m in messages]
    logger.info(
        f"[ensure_limit] ENTERED. Msgs: {len(messages)}, Types: {incoming_types}, Limit: {context_limit}, Effective: {effective_limit}"
    )

    if not messages or effective_limit <= 0:
        logger.warning("[ensure_limit] No messages or invalid limit, skipping.")
        return {"messages": []}

    target_tokens = int(effective_limit * TRIM_THRESHOLD_PERCENT)
    # --- Calculate tokens ONCE initially ---
    current_tokens = count_tokens(messages)
    logger.info(f"[ensure] токенов: {current_tokens} > {target_tokens}?")

    # Если всё в лимите — ни о чём не сообщаем
    if current_tokens <= target_tokens:
        logger.info("[ensure] лимит не превышен, выход")
        return {"messages": []}

    # --- Шаг 1. Удаляем старые не‑важные сообщения ---
    # Собираем ID для сохранения: summary и последнего
    summary_msgs = [
        m
        for m in messages
        if isinstance(m, SystemMessage) and m.name == HISTORY_SUMMARY_NAME
    ]
    preserved_ids = set(m.id for m in summary_msgs if hasattr(m, "id"))
    if messages:
        last = messages[-1]
        if hasattr(last, "id"):
            preserved_ids.add(last.id)
    logger.info(f"[ensure] сохраняем IDs: {preserved_ids}")

    # Рабочая копия списка
    working = messages.copy()
    removed_ids = set()
    i = 0
    # --- Recalculate tokens for the loop condition ---
    current_tokens = count_tokens(working)  # Initial count for the loop
    while current_tokens > target_tokens and i < len(working):
        msg = working[i]
        mid = getattr(msg, "id", None)
        should_pop = False  #
        if mid in preserved_ids:
            i += 1
        else:
            should_pop = True
            if mid:
                removed_ids.add(mid)
                logger.info(f"[ensure] removed id={mid}")
            # i не инкрементируем — список съехал

        if should_pop:
            working.pop(i)
            # --- Recalculate tokens AFTER modification ---
            current_tokens = count_tokens(working)
            logger.info(f"[ensure] after pop, tokens={current_tokens}")
        #

    updates: List[Any] = [RemoveMessage(id=rid) for rid in removed_ids]

    # --- Шаг 2. Усечение summary по ID, если всё ещё превышает ---
    if current_tokens > target_tokens and summary_msgs:
        logger.info("[ensure] удаление не помогло, усекаем summary")
        # находим заново индекс summary в trimmed списке
        for idx, m in enumerate(working):
            if (
                hasattr(m, "id")
                and m.id in preserved_ids
                and isinstance(m, SystemMessage)
                and m.name == HISTORY_SUMMARY_NAME
            ):
                original_msg = m  # Keep original message for comparison later
                current_msg_in_working = m  # This will be modified
                original_content = m.content or ""
                content_to_truncate = original_content

                current_tokens = count_tokens(working)  # Initial count for inner loop
                truncated_during_loop = False  # Flag to check if truncation happened

                logger.debug(
                    f"[ensure] Summary While Check: current_tokens={current_tokens}, target={target_tokens}, "
                    f"len(content_to_truncate)={len(content_to_truncate)}, MIN_CONTENT_LEN={MIN_CONTENT_LEN}"
                )
                while len(content_to_truncate) > MIN_CONTENT_LEN:  # Check length only
                    cut = max(
                        int(len(content_to_truncate) * CHUNK_REDUCTION_FACTOR), 100
                    )
                    content_to_truncate = content_to_truncate[:-cut]
                    # Create the new message based on the *original* message object `m`
                    truncated_msg_obj = _create_truncated_message(
                        m, content_to_truncate + "..."
                    )
                    working[idx] = truncated_msg_obj  # Update the working list
                    current_msg_in_working = truncated_msg_obj  # Update the reference
                    # --- Recalculate tokens AFTER truncation ---
                    current_tokens = count_tokens(working)
                    logger.info(
                        f"[ensure] trunc summary id={m.id} to len={len(content_to_truncate)}, tokens={current_tokens}"
                    )
                    truncated_during_loop = True
                    # --- Check token limit INSIDE the loop ---
                    if current_tokens <= target_tokens:
                        logger.debug(
                            f"[ensure] Token limit reached ({current_tokens} <= {target_tokens}), breaking summary truncation loop."
                        )
                        break

                logger.debug(
                    f"[ensure] Summary Check Before Append: truncated={truncated_during_loop}, "
                    f"current_content_preview='{current_msg_in_working.content[:50]}...', "
                    f"original_content_preview='{original_content[:50]}...', "
                    f"updates_len_before={len(updates)}"
                )
                # Add to updates only if content actually changed compared to original
                if (
                    truncated_during_loop
                    and current_msg_in_working.content != original_content
                ):
                    logger.info(
                        f"[ensure] Appending truncated summary id={current_msg_in_working.id} to updates."
                    )
                    updates.append(current_msg_in_working)
                    logger.debug(
                        f"[ensure] Updates len after summary append: {len(updates)}, last appended: {updates[-1].id}"
                    )
                else:
                    logger.info(
                        "[ensure] Truncated summary not appended (conditions not met)."
                    )
                break  # Found and processed summary, exit outer loop

    # --- Шаг 3. Усечение последнего сообщения по ID, если всё ещё превышает ---
    if current_tokens > target_tokens and working:
        logger.info("[ensure] усечение summary не помогло, усекаем последнее")
        last_original = working[-1]
        if hasattr(last_original, "id"):
            idx = len(working) - 1
            current_msg_in_working = last_original  # This will be modified
            original_content = last_original.content or ""
            content_to_truncate = original_content
            truncated_during_loop = False  # Flag

            current_tokens = count_tokens(working)  # Initial count for inner loop
            logger.debug(
                f"[ensure] Last Msg While Check: current_tokens={current_tokens}, target={target_tokens}, "
                f"len(content_to_truncate)={len(content_to_truncate)}, MIN_CONTENT_LEN={MIN_CONTENT_LEN}"
            )
            while len(content_to_truncate) > MIN_CONTENT_LEN:  # Check length only
                cut = max(int(len(content_to_truncate) * CHUNK_REDUCTION_FACTOR), 100)
                content_to_truncate = content_to_truncate[:-cut]
                # Create based on the original last message object `last_original`
                truncated_msg_obj = _create_truncated_message(
                    last_original, content_to_truncate + "..."
                )
                working[idx] = truncated_msg_obj  # Update the working list
                current_msg_in_working = truncated_msg_obj  # Update the reference
                # --- Recalculate tokens AFTER truncation ---
                current_tokens = count_tokens(working)
                logger.info(
                    f"[ensure] trunc last id={last_original.id} to len={len(content_to_truncate)}, tokens={current_tokens}"
                )
                truncated_during_loop = True
                # --- Check token limit INSIDE the loop ---
                if current_tokens <= target_tokens:
                    logger.debug(
                        f"[ensure] Token limit reached ({current_tokens} <= {target_tokens}), breaking last msg truncation loop."
                    )
                    break

            logger.debug(
                f"[ensure] Last Msg Check Before Append: truncated={truncated_during_loop}, "
                f"current_content_preview='{current_msg_in_working.content[:50]}...', "
                f"original_content_preview='{original_content[:50]}...', "
                f"updates_len_before={len(updates)}"
            )
            # Add to updates only if content actually changed
            if (
                truncated_during_loop
                and current_msg_in_working.content != original_content
            ):
                logger.info(
                    f"[ensure] Appending truncated last msg id={current_msg_in_working.id} to updates."
                )
                updates.append(current_msg_in_working)
                logger.debug(
                    f"[ensure] Updates len after last msg append: {len(updates)}, last appended: {updates[-1].id}"
                )
            else:
                logger.info(
                    "[ensure] Truncated last msg not appended (conditions not met)."
                )

    if not updates:
        logger.warning("[ensure] не удалось уместить в лимит")
        return {"messages": []}

    logger.info(f"[ensure] возвращаем {len(updates)} инструкций")
    return {"messages": updates}
