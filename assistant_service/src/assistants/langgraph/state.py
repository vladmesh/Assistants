from typing import Annotated, Any, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from shared_models import QueueTrigger

# Import our custom reducer
from .reducers import custom_message_reducer

# --- State Definition ---


class AssistantState(TypedDict):
    """State for the assistant, including messages and dialog tracking."""

    messages: Annotated[Sequence[BaseMessage], custom_message_reducer]
    user_id: str  # ID of the user for API calls, etc.
    assistant_id: str  # ID of the assistant for API calls
    llm_context_size: int  # Token limit for the main LLM
    triggered_event: Optional[
        QueueTrigger
    ]  # Event that triggered the graph run (e.g., reminder)
    log_extra: Optional[Dict[str, Any]]  # Additional context for logging
    initial_message_id: Optional[
        int
    ]  # ID of the initial message in this run (for status updates)
    current_summary_content: Optional[str]  # Current summary text from DB/cache
    newly_summarized_message_ids: Optional[
        List[int]
    ]  # IDs of messages included in new summary
    user_facts: Optional[List[Dict[str, Any]]]  # User facts from DB/cache


# --- End State Definition ---
