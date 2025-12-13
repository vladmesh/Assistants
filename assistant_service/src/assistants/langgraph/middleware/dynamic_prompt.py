"""Middleware for dynamic system prompt generation."""

import logging
from collections.abc import Callable

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

from .state import AssistantAgentState

logger = logging.getLogger(__name__)


class DynamicPromptMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that generates dynamic system prompts based on state.

    Uses wrap_model_call to modify the system message before each model call.
    Injects memories and summary into the system prompt template.
    """

    state_schema = AssistantAgentState

    def __init__(self, system_prompt_template: str):
        super().__init__()
        self.system_prompt_template = system_prompt_template

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Modify the system message with dynamic content."""
        state = request.state
        log_extra = state.get("log_extra", {})

        # Get memories and summary from state
        relevant_memories = state.get("relevant_memories", [])
        current_summary = state.get("current_summary_content")

        # Format memories for prompt
        memories_str = (
            "\n".join(f"- {m.get('text', '')}" for m in relevant_memories)
            if relevant_memories
            else "Нет сохраненной информации о пользователе."
        )
        summary_str = (
            current_summary if current_summary else "Нет предыдущей истории диалога."
        )

        try:
            formatted_prompt = self.system_prompt_template.format(
                summary_previous=summary_str, memories=memories_str
            )
        except KeyError as e:
            logger.error(
                f"Missing key in system_prompt_template: {e}. Using template as is.",
                extra=log_extra,
            )
            formatted_prompt = self.system_prompt_template

        # Create new system message with formatted content
        new_system_message = SystemMessage(content=formatted_prompt)

        # Override the system message in the request
        return handler(request.override(system_message=new_system_message))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Async version of wrap_model_call."""
        state = request.state
        log_extra = state.get("log_extra", {})

        # Get memories and summary from state
        relevant_memories = state.get("relevant_memories", [])
        current_summary = state.get("current_summary_content")

        # Format memories for prompt
        memories_str = (
            "\n".join(f"- {m.get('text', '')}" for m in relevant_memories)
            if relevant_memories
            else "Нет сохраненной информации о пользователе."
        )
        summary_str = (
            current_summary if current_summary else "Нет предыдущей истории диалога."
        )

        try:
            formatted_prompt = self.system_prompt_template.format(
                summary_previous=summary_str, memories=memories_str
            )
        except KeyError as e:
            logger.error(
                f"Missing key in system_prompt_template: {e}. Using template as is.",
                extra=log_extra,
            )
            formatted_prompt = self.system_prompt_template

        # Create new system message with formatted content
        new_system_message = SystemMessage(content=formatted_prompt)

        # Override the system message in the request
        return await handler(request.override(system_message=new_system_message))
