"""Middleware for saving assistant responses to the database."""

import logging
from typing import Any
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from shared_models.api_schemas.message import MessageCreate, MessageUpdate

from services.rest_service import RestServiceClient

from .state import AssistantAgentState

logger = logging.getLogger(__name__)


class ResponseSaverMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that saves assistant responses to the database.

    Runs after each model call (after_model hook).
    Saves AI messages and tool messages to the database.
    """

    state_schema = AssistantAgentState

    def __init__(self, rest_client: RestServiceClient):
        super().__init__()
        self.rest_client = rest_client

    async def aafter_model(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Save the assistant's response to the database (async)."""
        log_extra = state.get("log_extra", {})
        user_id_str = state.get("user_id")
        assistant_id_str = state.get("assistant_id")
        initial_message_id = state.get("initial_message_id")

        if not user_id_str or not assistant_id_str:
            logger.error(
                "User ID or Assistant ID not found in state. Cannot save messages.",
                extra=log_extra,
            )
            await self._update_initial_message_status(
                initial_message_id, "error", log_extra
            )
            return None

        try:
            user_id = int(user_id_str)
            assistant_id = UUID(assistant_id_str)
        except ValueError:
            logger.error(
                f"Invalid User ID '{user_id_str}' or "
                f"Assistant ID '{assistant_id_str}' format.",
                extra=log_extra,
            )
            await self._update_initial_message_status(
                initial_message_id, "error", log_extra
            )
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        # Get the last message - should be the AI response
        last_message = messages[-1]

        # Only save AI and Tool messages
        if isinstance(last_message, HumanMessage):
            return None

        # Save the message
        await self._save_message(last_message, user_id, assistant_id, log_extra)

        return None

    async def _save_message(
        self,
        message: BaseMessage,
        user_id: int,
        assistant_id: UUID,
        log_extra: dict,
    ) -> None:
        """Save a single message to the database."""
        if isinstance(message, AIMessage):
            role = "assistant"
            content = message.content if message.content is not None else ""
            metadata: dict[str, Any] = {}

            if message.tool_calls:
                tool_calls_data = [
                    {"name": tc.get("name"), "id": tc.get("id"), "args": tc.get("args")}
                    for tc in message.tool_calls
                ]
                metadata["tool_calls"] = tool_calls_data

            message_payload = MessageCreate(
                user_id=user_id,
                assistant_id=assistant_id,
                role=role,
                content=content,
                content_type="text",
                status="processed",
                tool_call_id=None,
                meta_data=metadata if metadata else None,
            )

        elif isinstance(message, ToolMessage):
            role = "tool"
            content = str(message.content)
            metadata = {"tool_name": message.name}
            if message.additional_kwargs:
                metadata.update(message.additional_kwargs)

            message_payload = MessageCreate(
                user_id=user_id,
                assistant_id=assistant_id,
                role=role,
                content=content,
                content_type="text",
                status="processed",
                tool_call_id=message.tool_call_id,
                meta_data=metadata if metadata else None,
            )
        else:
            return

        try:
            saved = await self.rest_client.create_message(message_payload)
            if saved and saved.id:
                logger.info(
                    f"Successfully saved message to DB (ID: {saved.id}, Role: {role})",
                    extra=log_extra,
                )
            else:
                logger.error(
                    "Failed to save message: No ID returned from API",
                    extra=log_extra,
                )
        except Exception as e:
            logger.error(
                f"Error saving message (Role: {role}): {str(e)}",
                extra=log_extra,
                exc_info=True,
            )

    async def _update_initial_message_status(
        self, message_id: int | None, status: str, log_extra: dict
    ) -> None:
        """Update the status of the initial message."""
        if not message_id:
            return

        try:
            update_data = MessageUpdate(status=status)
            await self.rest_client.update_message(message_id, update_data)
            logger.info(
                f"Updated message status to '{status}' (ID: {message_id})",
                extra=log_extra,
            )
        except Exception as e:
            logger.error(
                f"Error updating message status: {str(e)}",
                extra=log_extra,
            )
