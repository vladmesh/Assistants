"""Middleware for loading conversation context from the database."""

from typing import Any

import structlog
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.runtime import Runtime

from services.rest_service import RestServiceClient

from .state import AssistantAgentState

logger = structlog.get_logger(__name__)

DEFAULT_HISTORY_LIMIT = 50


class ContextLoaderMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that loads conversation context from the database.

    Runs before the first model call (before_model hook).
    Loads historical messages and prepends them to state.messages.
    Uses _context_loaded flag in state to run only once per invocation.
    """

    state_schema = AssistantAgentState

    def __init__(
        self, rest_client: RestServiceClient, history_limit: int = DEFAULT_HISTORY_LIMIT
    ):
        super().__init__()
        self.rest_client = rest_client
        self.history_limit = history_limit

    async def abefore_model(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Load conversation context from the database (async).

        Only runs on the first model call (checks _context_loaded flag).
        """
        log_extra = state.get("log_extra", {})
        logger.debug("ContextLoaderMiddleware.abefore_model called", extra=log_extra)

        # Skip if context already loaded in this invocation
        if state.get("_context_loaded"):
            logger.debug("Context already loaded, skipping", extra=log_extra)
            return None

        user_id_str = state.get("user_id", "")
        assistant_id_str = state.get("assistant_id", "")

        if not user_id_str or not assistant_id_str:
            logger.error(
                "User ID or Assistant ID not found in state, cannot load context.",
                extra=log_extra,
            )
            return None

        # Convert user_id to int
        try:
            user_id = int(user_id_str)
        except ValueError:
            logger.error(
                f"Invalid User ID format '{user_id_str}', cannot load context.",
                extra=log_extra,
            )
            return None

        # Load historical messages
        messages: list[BaseMessage] = []
        try:
            raw_messages = await self.rest_client.get_messages(
                user_id=user_id,
                assistant_id=assistant_id_str,
                limit=self.history_limit,
                status="processed",
                sort_by="id",
                sort_order="asc",
            )

            # Convert to BaseMessage objects (only human and assistant messages)
            messages = [
                self._convert_db_message_to_langchain(msg)
                for msg in raw_messages
                if msg.role in ("human", "assistant")
            ]

            logger.info(
                f"Loaded {len(messages)} recent messages for user {user_id}",
                extra=log_extra,
            )
        except Exception as e:
            logger.error(f"Error loading messages: {str(e)}", extra=log_extra)

        # Get the pending message (the new input)
        pending_message = state.get("pending_message")

        # Set DB ID on pending_message if available
        initial_message_id = state.get("initial_message_id")
        if pending_message and initial_message_id:
            pending_message.id = str(initial_message_id)

        # Build full context: history from DB + pending message at the end
        if pending_message:
            full_context = messages + [pending_message]
        else:
            full_context = messages

        pending_count = "1 pending" if pending_message else "0 pending"
        logger.info(
            f"Loaded context: {len(messages)} from DB + "
            f"{pending_count} = {len(full_context)} total",
            extra=log_extra,
        )

        return {"messages": full_context, "_context_loaded": True}

    @staticmethod
    def _convert_db_message_to_langchain(db_message) -> BaseMessage:
        """Convert a database message to a LangChain message class.

        Only handles 'human' and 'assistant' roles.
        Tool messages and intermediate tool_calls are not stored in history.
        """
        content = db_message.content or ""
        msg_id = str(db_message.id)

        if db_message.role == "human":
            return HumanMessage(content=content, id=msg_id)
        else:  # assistant
            return AIMessage(content=content, id=msg_id)
