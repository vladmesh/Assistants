# assistant_service/src/assistants/langgraph/nodes/init_state.py

import logging
from typing import Any, Dict, List

from assistants.langgraph.state import AssistantState
from langchain_core.messages import BaseMessage, SystemMessage

logger = logging.getLogger(__name__)

# Constant for the name attribute of the primary system prompt message
# Helps distinguish it from other potential SystemMessages (like facts)
SYSTEM_PROMPT_NAME = "system_prompt"


async def init_state_node(
    state: AssistantState, system_prompt_text: str
) -> Dict[str, Any]:
    """Ensures the primary system prompt is the first message in the state.

    Reads from state:
        - messages: The current list of messages (potentially empty or loaded from checkpoint).

    Updates state:
        - messages: Prepends the system prompt if it's missing or not first.
    """
    messages = state.get("messages", [])
    user_id = state.get("user_id", "unknown")
    log_extra = {"user_id": user_id}

    should_add_prompt = False
    if not messages:
        # No messages yet, definitely add the prompt
        should_add_prompt = True
        logger.debug("Messages list empty, adding system prompt.", extra=log_extra)
    elif (
        not isinstance(messages[0], SystemMessage)
        or getattr(messages[0], "name", None) != SYSTEM_PROMPT_NAME
    ):
        # First message exists but isn't our specific system prompt
        # Remove any other message incorrectly placed at the start?
        # For now, just prepend, potentially resulting in duplicate system messages if handled improperly elsewhere
        should_add_prompt = True
        logger.debug(
            "First message is not the system prompt, prepending system prompt.",
            extra=log_extra,
        )
        # Optional: Remove existing message at index 0 if it's not the right one?
        # messages = messages[1:]

    if should_add_prompt:
        system_message = SystemMessage(
            content=system_prompt_text, name=SYSTEM_PROMPT_NAME
        )
        # Prepend the system message to the potentially modified list
        updated_messages = [system_message] + messages
        logger.info(
            f"System prompt added/prepended for user {user_id}.", extra=log_extra
        )
        return {"messages": updated_messages}
    else:
        # System prompt is already correctly placed
        logger.debug("System prompt already present at the start.", extra=log_extra)
        return {}  # No changes needed
