"""Middleware for retrieving relevant memories from RAG service."""

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

from services.rag_service import RagServiceClient

from .state import AssistantAgentState

logger = logging.getLogger(__name__)


class MemoryRetrievalMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that retrieves relevant memories from the RAG service.

    Runs before each model call (before_model hook).
    Adds relevant_memories to state for use in system prompt.
    """

    state_schema = AssistantAgentState

    def __init__(
        self,
        rag_client: RagServiceClient,
        limit: int = 5,
        threshold: float = 0.6,
    ):
        super().__init__()
        self.rag_client = rag_client
        self.limit = limit
        self.threshold = threshold

    async def abefore_model(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Retrieve relevant memories based on the conversation (async)."""
        user_id_str = state.get("user_id", "")
        log_extra = state.get("log_extra", {})

        if not user_id_str:
            logger.warning(
                "No user_id in state, skipping memory retrieval", extra=log_extra
            )
            return None

        # Get the last human message for query
        messages = state.get("messages", [])
        query = None
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                query = msg.content
                break

        if not query or not query.strip():
            logger.debug(
                "No message content found, skipping memory retrieval", extra=log_extra
            )
            return None

        # Convert user_id to int
        try:
            user_id = int(user_id_str)
        except ValueError:
            logger.error(
                f"Invalid user_id format: {user_id_str}, skipping memory retrieval",
                extra=log_extra,
            )
            return None

        # Retrieve memories from RAG service
        try:
            memories = await self.rag_client.search_memories(
                query=query,
                user_id=user_id,
                limit=self.limit,
                threshold=self.threshold,
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
            return None
