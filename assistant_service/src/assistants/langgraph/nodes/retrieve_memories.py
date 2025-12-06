"""Node for retrieving relevant memories from Memory V2 (RAG service)."""

import logging
from typing import Any

from assistants.langgraph.state import AssistantState
from services.rag_service import RagServiceClient

logger = logging.getLogger(__name__)


async def retrieve_memories_node(
    state: AssistantState,
    rag_client: RagServiceClient,
    limit: int = 5,
    threshold: float = 0.6,
) -> dict[str, Any]:
    """
    Retrieves relevant memories based on the incoming message.
    Adds them to the state for use in system prompt.

    Args:
        state: Current assistant state containing user_id and initial_message.
        rag_client: Client for RAG service API.
        limit: Maximum number of memories to retrieve (from GlobalSettings).
        threshold: Minimum similarity threshold (from GlobalSettings).

    Returns:
        Dict with relevant_memories list to merge into state.
    """
    user_id_str = state.get("user_id", "")
    initial_message = state.get("initial_message")
    log_extra = state.get("log_extra", {})

    # Validate required fields
    if not user_id_str:
        logger.warning(
            "No user_id in state, skipping memory retrieval", extra=log_extra
        )
        return {"relevant_memories": []}

    if not initial_message:
        logger.warning(
            "No initial_message in state, skipping memory retrieval", extra=log_extra
        )
        return {"relevant_memories": []}

    # Convert user_id to int
    try:
        user_id = int(user_id_str)
    except ValueError:
        logger.error(
            f"Invalid user_id format: {user_id_str}, skipping memory retrieval",
            extra=log_extra,
        )
        return {"relevant_memories": []}

    # Extract query from message content
    query = initial_message.content
    if not query or not query.strip():
        logger.debug(
            "Empty message content, skipping memory retrieval", extra=log_extra
        )
        return {"relevant_memories": []}

    # Retrieve memories from RAG service
    try:
        memories = await rag_client.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            threshold=threshold,
        )

        logger.info(
            f"Retrieved {len(memories)} relevant memories for user {user_id}",
            extra={**log_extra, "memories_count": len(memories)},
        )

        return {"relevant_memories": memories}

    except Exception as e:
        logger.error(
            f"Error retrieving memories: {e}",
            extra=log_extra,
            exc_info=True,
        )
        # Return empty list on error - don't fail the whole flow
        return {"relevant_memories": []}
