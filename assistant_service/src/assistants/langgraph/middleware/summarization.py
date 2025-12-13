"""Middleware for summarizing conversation history."""

import json
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, RemoveMessage, SystemMessage
from langgraph.runtime import Runtime

from assistants.langgraph.utils.token_counter import count_tokens
from services.rest_service import RestServiceClient

from .state import AssistantAgentState

logger = logging.getLogger(__name__)

SUMMARY_THRESHOLD_PERCENT = 0.6
MESSAGES_TO_KEEP_TAIL = 5


class SummarizationMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that summarizes conversation history when context is too large.

    Uses wrap_model_call to check context size before each model call
    and summarize if needed.
    """

    state_schema = AssistantAgentState

    def __init__(
        self,
        summary_llm: BaseChatModel,
        rest_client: RestServiceClient,
        summarization_prompt: str,
        system_prompt_template: str,
        threshold_percent: float = SUMMARY_THRESHOLD_PERCENT,
        messages_to_keep: int = MESSAGES_TO_KEEP_TAIL,
    ):
        super().__init__()
        self.summary_llm = summary_llm
        self.rest_client = rest_client
        self.summarization_prompt = summarization_prompt
        self.system_prompt_template = system_prompt_template
        self.threshold_percent = threshold_percent
        self.messages_to_keep = messages_to_keep

    async def abefore_model(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Check if summarization is needed and perform it (async)."""
        log_extra = state.get("log_extra", {})
        messages = state.get("messages", [])
        context_limit = state.get("llm_context_size", 0)

        if not messages or context_limit <= 0:
            return None

        # Check if we need to summarize
        if not self._should_summarize(state, context_limit, log_extra):
            return None

        # Perform summarization
        return await self._summarize_history(state, log_extra)

    def _should_summarize(
        self,
        state: AssistantAgentState,
        context_limit: int,
        log_extra: dict,
    ) -> bool:
        """Check if summarization is needed based on token count."""
        messages = state.get("messages", [])

        # Estimate system message tokens
        cached_summary = state.get("current_summary_content")
        cached_memories = state.get("relevant_memories", [])

        memories_str = (
            "\n".join(f"- {m.get('text', '')}" for m in cached_memories)
            if cached_memories
            else "Нет сохраненной информации."
        )
        summary_str = (
            cached_summary if cached_summary else "Нет предыдущей истории диалога."
        )

        try:
            formatted_prompt_content = self.system_prompt_template.format(
                summary_previous=summary_str, memories=memories_str
            )
            temp_system_message = SystemMessage(content=formatted_prompt_content)
            system_prompt_tokens = count_tokens([temp_system_message])
        except Exception as e:
            logger.error(
                f"Error formatting temp system prompt: {e}. Assuming 0 tokens.",
                extra=log_extra,
            )
            system_prompt_tokens = 0

        history_tokens = count_tokens(messages)
        total_estimated_tokens = system_prompt_tokens + history_tokens
        ratio = total_estimated_tokens / context_limit if context_limit else 0

        should_summarize = ratio >= self.threshold_percent

        decision = "summarize" if should_summarize else "skip"
        logger.info(
            f"[should_summarize] Tokens={total_estimated_tokens}, "
            f"Limit={context_limit}, Ratio={ratio:.2f}, "
            f"Threshold={self.threshold_percent:.2f}, Decision={decision}",
            extra=log_extra,
        )

        return should_summarize

    async def _summarize_history(
        self, state: AssistantAgentState, log_extra: dict
    ) -> dict[str, Any] | None:
        """Perform the summarization."""
        messages = state.get("messages", [])

        # Select messages to summarize
        head_msgs, message_ids = self._select_messages(messages)
        if not head_msgs:
            logger.warning("No messages selected for summarization.", extra=log_extra)
            return None

        # Get existing summary
        prev_summary = state.get("current_summary_content")

        # Create JSON chunk
        chunk_json = self._make_json_chunk(head_msgs)
        if not chunk_json:
            return None

        # Create prompt
        prompt = self._create_prompt(prev_summary, chunk_json)

        # Call LLM
        try:
            response = await self.summary_llm.ainvoke(prompt)
            summary_text = (
                response.content if hasattr(response, "content") else str(response)
            )
        except Exception as e:
            logger.error(f"Error generating summary: {e}", extra=log_extra)
            return None

        if not summary_text:
            return None

        # Create remove instructions for summarized messages
        remove_instructions = [RemoveMessage(id=msg_id) for msg_id in message_ids]

        logger.info(
            f"Created {len(remove_instructions)} RemoveMessage instructions",
            extra=log_extra,
        )

        return {
            "messages": remove_instructions,
            "current_summary_content": summary_text,
            "newly_summarized_message_ids": message_ids,
        }

    def _select_messages(
        self, messages: list[BaseMessage]
    ) -> tuple[list[BaseMessage], list[str]]:
        """Select head messages to summarize and their IDs."""
        non_system_messages = [
            (i, m) for i, m in enumerate(messages) if not isinstance(m, SystemMessage)
        ]

        if len(non_system_messages) <= self.messages_to_keep:
            return [], []

        head_part = non_system_messages[: -self.messages_to_keep]
        head_msgs = [m for _, m in head_part]
        message_ids = [m.id for _, m in head_part if m.id]

        return head_msgs, message_ids

    @staticmethod
    def _make_json_chunk(messages: list[BaseMessage]) -> str:
        """Serialize messages to JSON for summarization prompt."""
        data = []
        for msg in messages:
            content = getattr(msg, "content", "")
            if not content:
                continue
            entry = {
                "type": type(msg).__name__.replace("Message", ""),
                "Content": content,
            }
            name = getattr(msg, "name", None)
            if name:
                entry["Name"] = name
            data.append(entry)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _create_prompt(self, prev_summary: str | None, chunk_json: str) -> str:
        """Create the summarization prompt."""
        return self.summarization_prompt.format(
            json=chunk_json,
            current_summary=prev_summary or "No existing summary.",
        )
