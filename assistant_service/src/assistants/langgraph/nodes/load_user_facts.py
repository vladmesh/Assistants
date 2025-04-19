# assistant_service/src/assistants/langgraph/nodes/load_user_facts.py

import logging
from typing import Any, Dict, List

# Import state definition and token counter utility
from assistants.langgraph.state import AssistantState
from assistants.langgraph.utils.token_counter import count_tokens
from langchain_core.messages import BaseMessage, SystemMessage

logger = logging.getLogger(__name__)

# Constants matching those in init_state.py
FACTS_MESSAGE_NAME = "user_facts"
SYSTEM_PROMPT_NAME = "system_prompt"  # Define the constant here as well


async def load_user_facts_node(state: AssistantState) -> Dict[str, Any]:
    # Log the incoming state
    logger.debug(
        f"Entering load_user_facts_node with state: {state}",
        extra=state.get("log_extra", {}),
    )

    """Formats facts from pending_facts into a SystemMessage and adds/replaces it in messages.
    Updates the token count.
    
    Reads from state:
        - pending_facts: List of facts fetched by the previous node.
        - messages: The current list of messages.
        - current_token_count: The last known token count (optional).
        
    Updates state:
        - messages: Updated list with the facts SystemMessage added/replaced.
        - pending_facts: Cleared list.
        - facts_loaded: Set to True if facts were loaded, False otherwise.
        - current_token_count: Updated token count.
    """
    pending_facts = state.get("pending_facts", [])
    current_messages = state.get("messages", [])
    user_id = state.get("user_id", "unknown")  # For logging
    log_extra = {"user_id": user_id}

    if not pending_facts:
        logger.debug(f"No pending facts to load for user {user_id}.", extra=log_extra)
        # If facts weren't loaded, ensure the flag is False
        # Keep existing token count if available
        return {
            "facts_loaded": False,
            "current_token_count": state.get("current_token_count"),
        }

    logger.info(
        f"Loading {len(pending_facts)} facts into messages for user {user_id}.",
        extra=log_extra,
    )

    # Format the facts into a message string
    # Using explicit newlines for clarity in the message content
    facts_content = "Current user facts:\n" + "\n".join(
        f"- {fact}" for fact in pending_facts
    )
    facts_message = SystemMessage(content=facts_content, name=FACTS_MESSAGE_NAME)

    # Remove any previous facts message
    updated_messages: List[BaseMessage] = [
        msg
        for msg in current_messages
        if getattr(msg, "name", None) != FACTS_MESSAGE_NAME
    ]

    # Find the index to insert facts: after the system prompt, otherwise at the start
    insert_index = 0
    if (
        updated_messages
        and isinstance(updated_messages[0], SystemMessage)
        and getattr(updated_messages[0], "name", None) == SYSTEM_PROMPT_NAME
    ):
        insert_index = 1  # Insert after the system prompt

    # Insert the new facts message at the calculated index
    updated_messages.insert(insert_index, facts_message)

    # Recalculate token count for the modified message list
    new_token_count = count_tokens(updated_messages)
    logger.debug(
        f"Updated token count after loading facts: {new_token_count}", extra=log_extra
    )

    state_update = {
        "messages": updated_messages,
        "pending_facts": [],  # Clear pending facts after loading
        "facts_loaded": True,  # Mark facts as loaded for this cycle
        "current_token_count": new_token_count,
    }

    # Log the returned state update
    logger.debug(
        f"Returning state update from load_user_facts_node: {state_update}",
        extra=log_extra,
    )
    return state_update
