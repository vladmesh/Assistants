"""Middleware for finalizing message processing."""

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime
from shared_models.api_schemas.message import MessageUpdate

from services.rest_service import RestServiceClient

from .state import AssistantAgentState

logger = logging.getLogger(__name__)


class FinalizerMiddleware(AgentMiddleware[AssistantAgentState]):
    """Middleware that finalizes message processing.

    Runs after the agent completes (after_agent hook).
    Updates the initial message status to 'processed' or 'error'.
    """

    state_schema = AssistantAgentState

    def __init__(self, rest_client: RestServiceClient):
        super().__init__()
        self.rest_client = rest_client

    async def aafter_agent(
        self, state: AssistantAgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """Finalize processing by updating message status (async)."""
        log_extra = state.get("log_extra", {})
        initial_message_id = state.get("initial_message_id")

        if not initial_message_id:
            logger.debug(
                "No initial_message_id, skipping status update", extra=log_extra
            )
            return None

        # Check if there was an error
        error_occurred = state.get("error_occurred", False)
        status = "error" if error_occurred else "processed"

        try:
            update_data = MessageUpdate(status=status)
            updated = await self.rest_client.update_message(
                initial_message_id, update_data
            )
            if updated:
                logger.info(
                    f"Updated message status to '{status}' (ID: {initial_message_id})",
                    extra=log_extra,
                )
            else:
                logger.warning(
                    f"Failed to update message status to '{status}' "
                    f"(ID: {initial_message_id})",
                    extra=log_extra,
                )
        except Exception as e:
            logger.error(
                f"Error updating message status: {str(e)}",
                extra=log_extra,
                exc_info=True,
            )

        return None
