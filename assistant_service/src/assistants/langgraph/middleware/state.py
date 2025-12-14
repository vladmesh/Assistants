"""Custom state schema for the assistant agent."""

from typing import Any, NotRequired

from langchain.agents import AgentState
from langchain_core.messages import BaseMessage
from shared_models import QueueTrigger


class AssistantAgentState(AgentState):
    """Extended state for assistant with custom fields.

    Inherits from AgentState which provides:
    - messages: Annotated[Sequence[BaseMessage], add_messages]

    Custom fields for our assistant:
    - pending_message: Incoming message to process (added to messages by middleware)
    - initial_message: The incoming message that triggered this invocation
    - user_id: User ID for API calls and context
    - assistant_id: Assistant ID for API calls
    - llm_context_size: Token limit for the main LLM context window
    - triggered_event: Event that triggered the run (e.g., reminder)
    - log_extra: Additional context for logging
    - initial_message_id: DB ID of the initial message (set by MessageSaverMiddleware)
    - current_summary_content: Current summary text
    - newly_summarized_message_ids: IDs of messages included in new summary
    - relevant_memories: Retrieved memories from RAG service
    """

    pending_message: NotRequired[BaseMessage | None]
    initial_message: NotRequired[BaseMessage | None]
    user_id: NotRequired[str | None]
    assistant_id: NotRequired[str | None]
    llm_context_size: NotRequired[int | None]
    triggered_event: NotRequired[QueueTrigger | None]
    log_extra: NotRequired[dict[str, Any] | None]
    initial_message_id: NotRequired[int | None]
    current_summary_content: NotRequired[str | None]
    newly_summarized_message_ids: NotRequired[list[int] | None]
    relevant_memories: NotRequired[list[dict[str, Any]] | None]
    error_occurred: NotRequired[bool | None]
    # Internal flags for middleware to run only once per invocation
    _context_loaded: NotRequired[bool | None]
    _message_saved: NotRequired[bool | None]
