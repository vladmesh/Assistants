from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, Sequence

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from shared_models import QueueTrigger

# Import our custom reducer
from .reducers import custom_message_reducer


# --- State Definition ---
def update_dialog_stack(
    new_state: List[str], current_stack: Optional[List[str]]
) -> List[str]:
    """Helper to manage the dialog state stack."""
    if current_stack is None:
        return new_state
    # Simple replacement logic for now, could be more complex (push/pop)
    return new_state


class AssistantState(TypedDict):
    """State for the assistant, including messages and dialog tracking."""

    messages: Annotated[Sequence[BaseMessage], custom_message_reducer]
    user_id: str  # ID of the user for API calls, etc.
    llm_context_size: int  # Token limit for the main LLM
    triggered_event: QueueTrigger  # Event that triggered the graph run (e.g., reminder)
    last_summary_ts: Optional[datetime]  # Timestamp of the last summary
    log_extra: Optional[Dict[str, Any]]  # Additional context for logging
    dialog_state: Optional[List[str]]  # Stack for tracking dialog states (optional)


# --- End State Definition ---
