"""Middleware for saving incoming messages to the database."""

from typing import Any
from uuid import UUID

import structlog
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from shared_models.api_schemas.message import MessageCreate

from services.rest_service import RestServiceClient

from .state import AssistantAgentState

logger = structlog.get_logger(__name__)


class MessageSaverMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that saves incoming messages to the database.

    Runs before the first model call (before_model hook).
    Sets initial_message_id in state for later reference.
    Uses _message_saved flag in state to run only once per invocation.
    """

    state_schema = AssistantAgentState

    def __init__(self, rest_client: RestServiceClient, message_id_callback: Any = None):
        super().__init__()
        self.rest_client = rest_client
        self.message_id_callback = message_id_callback

    async def abefore_model(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Save the input message to the database (async).

        Only runs on the first model call (checks _message_saved flag).
        """
        log_extra = state.get("log_extra", {})
        logger.debug("MessageSaverMiddleware.abefore_model called", extra=log_extra)

        # Skip if message already saved in this invocation
        if state.get("_message_saved"):
            logger.debug("Message already saved, skipping", extra=log_extra)
            return None
        user_id_str = state.get("user_id", "")
        assistant_id_str = state.get("assistant_id", "")

        if not user_id_str or not assistant_id_str:
            logger.error(
                "User ID or Assistant ID not found in state, cannot save message.",
                extra=log_extra,
            )
            return None

        # Get the pending message (the new input)
        input_message = state.get("pending_message")
        if not input_message:
            logger.warning(
                "No pending_message in state, nothing to save.", extra=log_extra
            )
            return None

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
            meta_data={},
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
                # Call callback if provided to store initial_message_id
                # for error handling
                if self.message_id_callback:
                    try:
                        self.message_id_callback(saved_message.id)
                    except Exception as callback_error:
                        logger.warning(
                            f"Error calling message_id_callback: {callback_error}",
                            extra=log_extra,
                        )
                return {
                    "initial_message_id": saved_message.id,
                    "initial_message": input_message,
                    "_message_saved": True,
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
