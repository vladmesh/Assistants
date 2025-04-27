from typing import Annotated, Any, Dict, Optional, Sequence

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
    llm_context_size: int  # Token limit for the main LLM
    triggered_event: QueueTrigger  # Event that triggered the graph run (e.g., reminder)
    log_extra: Optional[Dict[str, Any]]  # Additional context for logging


# --- End State Definition ---
