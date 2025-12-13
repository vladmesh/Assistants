"""Middleware for loading conversation context from the database."""

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from services.rest_service import RestServiceClient

from .state import AssistantAgentState

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_LIMIT = 50


class ContextLoaderMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that loads conversation context from the database.

    Runs before the agent starts (before_agent hook).
    Loads historical messages and prepends them to state.messages.
    """

    state_schema = AssistantAgentState

    def __init__(
        self, rest_client: RestServiceClient, history_limit: int = DEFAULT_HISTORY_LIMIT
    ):
        super().__init__()
        self.rest_client = rest_client
        self.history_limit = history_limit

    async def abefore_agent(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Load conversation context from the database (async)."""
        user_id_str = state.get("user_id", "")
        assistant_id_str = state.get("assistant_id", "")
        log_extra = state.get("log_extra", {})

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

            # Convert to BaseMessage objects
            messages = [
                self._convert_db_message_to_langchain(msg) for msg in raw_messages
            ]
            logger.info(
                f"Loaded {len(messages)} recent messages for user {user_id}",
                extra=log_extra,
            )
        except Exception as e:
            logger.error(f"Error loading messages: {str(e)}", extra=log_extra)

        if not messages:
            return None

        # Get current messages (the new input message)
        current_messages = list(state.get("messages", []))

        # Set DB ID on initial_message if available
        initial_message_id = state.get("initial_message_id")
        if current_messages and initial_message_id:
            current_messages[-1].id = str(initial_message_id)

        # Prepend historical messages to current messages
        full_context = messages + current_messages

        logger.info(
            f"Loaded context contains {len(full_context)} messages", extra=log_extra
        )

        return {"messages": full_context}

    @staticmethod
    def _convert_db_message_to_langchain(db_message) -> BaseMessage:
        """Convert a database message to a LangChain message class."""
        content = db_message.content or ""
        msg_id = str(db_message.id)

        if db_message.role == "human":
            return HumanMessage(content=content, id=msg_id)
        elif db_message.role == "assistant":
            return AIMessage(content=content, id=msg_id)
        elif db_message.role == "tool":
            tool_call_id = (
                str(db_message.tool_call_id) if db_message.tool_call_id else None
            )
            return ToolMessage(
                content=content,
                tool_call_id=tool_call_id,
                id=msg_id,
            )
        else:
            logger.warning(
                f"Unknown message role: {db_message.role}, treating as human message"
            )
            return HumanMessage(content=content, id=msg_id)
