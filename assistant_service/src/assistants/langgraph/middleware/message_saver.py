"""Middleware for saving incoming messages to the database."""

import logging
from typing import Any
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from shared_models.api_schemas.message import MessageCreate

from services.rest_service import RestServiceClient

from .state import AssistantAgentState

logger = logging.getLogger(__name__)


class MessageSaverMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that saves incoming messages to the database.

    Runs before the agent starts (before_agent hook).
    Sets initial_message_id in state for later reference.
    """

    state_schema = AssistantAgentState

    def __init__(self, rest_client: RestServiceClient):
        super().__init__()
        self.rest_client = rest_client

    async def abefore_agent(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Save the input message to the database before agent starts (async)."""
        log_extra = state.get("log_extra", {})
        user_id_str = state.get("user_id", "")
        assistant_id_str = state.get("assistant_id", "")

        if not user_id_str or not assistant_id_str:
            logger.error(
                "User ID or Assistant ID not found in state, cannot save message.",
                extra=log_extra,
            )
            return None

        # Get the last message (should be the new input)
        messages = state.get("messages", [])
        if not messages:
            logger.warning("No messages in state, nothing to save.", extra=log_extra)
            return None

        input_message = messages[-1]

        # Convert user_id to int
        try:
            user_id = int(user_id_str)
        except ValueError:
            logger.error(
                f"Invalid User ID format '{user_id_str}', cannot save message.",
                extra=log_extra,
            )
            return None

        # Convert assistant_id to UUID
        try:
            assistant_id = UUID(assistant_id_str)
        except ValueError:
            logger.error(
                f"Invalid Assistant ID format '{assistant_id_str}', "
                "cannot save message.",
                extra=log_extra,
            )
            return None

        # Map LangChain message type to role
        role = self._get_role_from_message(input_message)

        # Prepare message data
        message_data = MessageCreate(
            user_id=user_id,
            assistant_id=assistant_id,
            role=role,
            content=input_message.content,
            content_type="text",
            status="pending_processing",
            tool_call_id=None,
            metadata={},
        )

        # Special handling for tool messages
        if hasattr(input_message, "tool_call_id") and input_message.tool_call_id:
            message_data.tool_call_id = input_message.tool_call_id

        # Save message to database
        try:
            saved_message = await self.rest_client.create_message(message_data)
            if saved_message and saved_message.id:
                logger.info(
                    f"Saved input message (ID: {saved_message.id}, Role: {role})",
                    extra=log_extra,
                )
                return {
                    "initial_message_id": saved_message.id,
                    "initial_message": input_message,
                }
            else:
                logger.error(
                    "Failed to save message: No ID returned from API", extra=log_extra
                )
        except Exception as e:
            logger.error(
                f"Error saving input message: {str(e)}", extra=log_extra, exc_info=True
            )

        return None

    @staticmethod
    def _get_role_from_message(message: BaseMessage) -> str:
        """Maps a LangChain message type to a database role."""
        if isinstance(message, HumanMessage):
            return "human"
        elif isinstance(message, AIMessage):
            return "assistant"
        elif isinstance(message, ToolMessage):
            return "tool_response"
        else:
            return "human"
