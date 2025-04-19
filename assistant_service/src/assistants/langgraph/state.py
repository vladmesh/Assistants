from datetime import datetime
from typing import Annotated, Any, List, Literal, Optional

from langgraph.graph.message import AnyMessage
from typing_extensions import TypedDict


# --- State Definition ---
def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        # Ensure we don't pop from an empty list or the initial 'idle'
        if len(left) > 1:
            return left[:-1]
        return left  # Return as is if only 'idle' or empty
    return left + [right]


class AssistantState(TypedDict):
    """State for the assistant, including messages and dialog tracking."""

    messages: list[AnyMessage]
    user_id: Optional[str]  # Keep track of the user ID
    # Add field for external trigger events like reminders
    triggered_event: Optional[dict] = None

    dialog_state: Annotated[
        # Add more states if needed, keep simple for now
        list[Literal["idle", "processing", "waiting_for_tool", "error", "timeout"]],
        update_dialog_stack,
    ]
    last_activity: datetime  # Track last activity for timeout purposes

    # Add fields from memory_plan.md
    pending_facts: Optional[List[str]] = None
    facts_loaded: bool = False
    last_summary_ts: Optional[datetime] = None
    llm_context_size: Optional[int] = None
    fact_added_in_last_run: bool = False
    current_token_count: Optional[int] = None


# --- End State Definition ---
