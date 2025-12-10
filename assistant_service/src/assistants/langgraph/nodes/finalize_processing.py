import logging
from typing import Any

from shared_models.api_schemas.message import MessageUpdate

from assistants.langgraph.state import AssistantState
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)


async def finalize_processing_node(
    state: AssistantState, rest_client: RestServiceClient
) -> dict[str, Any]:
    """
    Finalizes message processing by:
    1. Updating initial message status to 'processed' or 'error'
    2. Performing any cleanup operations

    Note: Summary is kept in-memory only. Messages are not linked to summaries.
    """
    log_extra = state.get("log_extra", {})
    initial_message_id = state.get("initial_message_id")

    logger.debug("[finalize_processing_node] Finalizing message processing")

    # Check if initial message needs error status update
    # This would happen if we had an error during processing but still reached this node
    if initial_message_id and state.get("error_occurred", False):
        try:
            update_data = MessageUpdate(status="error")
            updated = await rest_client.update_message(initial_message_id, update_data)
            if updated:
                logger.info(
                    f"Updated message status to 'error' (ID: {initial_message_id})",
                    extra=log_extra,
                )
            else:
                logger.warning(
                    f"Failed to update message error status (ID: {initial_message_id})",
                    extra=log_extra,
                )
        except Exception as e:
            logger.error(
                f"Error updating message error status: {str(e)}", extra=log_extra
            )
    # Обновление статуса сообщения на "processed" при успешной обработке
    elif initial_message_id:
        try:
            update_data = MessageUpdate(status="processed")
            updated = await rest_client.update_message(initial_message_id, update_data)
            if updated:
                logger.info(
                    f"Updated message status to 'processed' (ID: {initial_message_id})",
                    extra=log_extra,
                )
            else:
                logger.warning(
                    "Failed to update message status to 'processed' "
                    f"(ID: {initial_message_id})",
                    extra=log_extra,
                )
        except Exception as e:
            logger.error(
                f"Error updating message processed status: {str(e)}", extra=log_extra
            )

    return state
