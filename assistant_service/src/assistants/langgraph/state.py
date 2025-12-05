from collections.abc import Sequence
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from shared_models import QueueTrigger
from typing_extensions import TypedDict

# Import our custom reducer
from .reducers import custom_message_reducer

# --- State Definition ---


class AssistantState(TypedDict):
    """State for the assistant, including messages and dialog tracking."""

    messages: Annotated[Sequence[BaseMessage], custom_message_reducer]
    initial_message: BaseMessage  # Входящее сообщение
    user_id: str  # ID of the user for API calls, etc.
    assistant_id: str  # ID of the assistant for API calls
    llm_context_size: int  # Token limit for the main LLM
    triggered_event: (
        QueueTrigger | None
    )  # Event that triggered the graph run (e.g., reminder)
    log_extra: dict[str, Any] | None  # Additional context for logging
    initial_message_id: (
        int | None
    )  # ID of the initial message in this run (for status updates)
    current_summary_content: str | None  # Current summary text from DB/cache
    newly_summarized_message_ids: (
        list[int] | None
    )  # IDs of messages included in new summary
    user_facts: list[dict[str, Any]] | None  # User facts from DB/cache


# --- End State Definition ---
