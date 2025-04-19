# assistant_service/src/assistants/langgraph/nodes/entry_check_facts.py

import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

# Import necessary components from your project
# Adjust paths as needed
from assistants.langgraph.state import AssistantState
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)


async def entry_check_facts_node(
    state: AssistantState, rest_client: RestServiceClient
) -> Dict[str, Any]:
    """Checks if user facts need refreshing and fetches them using RestServiceClient.

    Reads from state:
        - user_id: The ID of the current user.
        - facts_loaded: Boolean flag indicating if facts were loaded previously in this session.
        - fact_added_in_last_run: Boolean flag indicating if a fact was added by the agent recently.

    Updates state:
        - pending_facts: List of facts fetched from the API (or empty list).
        - fact_added_in_last_run: Resets this flag to False.
    """
    user_id = state.get("user_id")
    if not user_id:
        logger.error("entry_check_facts_node called without user_id in state.")
        # Cannot fetch facts without user_id, return default update
        return {"pending_facts": [], "fact_added_in_last_run": False}

    # Determine if facts need to be refreshed
    # Refresh if facts haven't been loaded yet OR if a fact was added in the last run
    should_refresh = not state.get("facts_loaded", False) or state.get(
        "fact_added_in_last_run", False
    )
    # TODO: Potentially add other conditions like TTL (Time To Live) for facts

    log_extra = {"user_id": user_id, "should_refresh": should_refresh}
    logger.debug(f"Entering entry_check_facts_node", extra=log_extra)

    if should_refresh:
        logger.info(f"Refreshing user facts for user {user_id}.", extra=log_extra)
        try:
            # Directly call the rest_client method passed during graph setup
            retrieved_facts = await rest_client.get_user_facts(user_id=user_id)

            if isinstance(retrieved_facts, list):
                logger.info(
                    f"Successfully fetched {len(retrieved_facts)} facts for user {user_id}.",
                    extra=log_extra,
                )
                # Return the facts and reset the flag
                return {
                    "pending_facts": retrieved_facts,
                    "fact_added_in_last_run": False,
                }
            else:
                logger.warning(
                    f"Received unexpected data type from get_user_facts for user {user_id}: {type(retrieved_facts)}",
                    extra=log_extra,
                )
                # Treat unexpected type as no facts found
                return {"pending_facts": [], "fact_added_in_last_run": False}

        except Exception as e:
            logger.exception(
                f"Error fetching facts for user {user_id}: {e}",
                exc_info=True,
                extra=log_extra,
            )
            # On error, proceed without facts and reset the flag
            return {"pending_facts": [], "fact_added_in_last_run": False}
    else:
        # No refresh needed, return empty pending facts and reset flag
        logger.debug(f"Fact refresh not needed for user {user_id}.", extra=log_extra)
        state_update = {"pending_facts": [], "fact_added_in_last_run": False}

    # Log the returned state update
    logger.debug(
        f"Returning state update from entry_check_facts_node: {state_update}",
        extra=log_extra,
    )
    return state_update
