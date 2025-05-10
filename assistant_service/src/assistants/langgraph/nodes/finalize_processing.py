import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from assistants.langgraph.state import AssistantState
from services.rest_service import RestServiceClient

from shared_models.api_schemas.message import MessageUpdate

logger = logging.getLogger(__name__)


async def finalize_processing_node(
    state: AssistantState, rest_client: RestServiceClient
) -> Dict[str, Any]:
    """
    Finalizes message processing by:
    1. Updating statuses for summarized messages if summary was created
    2. Handling any errors in processing
    3. Performing any cleanup operations

    This node should be the last one in the graph, after all other processing is done.
    """
    logger.info("[finalize_processing_node] Finalizing message processing")

    # Extract necessary IDs and data
    user_id_str = state.get("user_id", "")
    assistant_id_str = state.get("assistant_id", "")
    initial_message_id = state.get("initial_message_id")
    newly_summarized_message_ids = state.get("newly_summarized_message_ids", [])
    log_extra = state.get("log_extra", {})

    # Input validation
    if not user_id_str or not assistant_id_str:
        logger.error(
            "User ID or Assistant ID not found in state, cannot finalize processing.",
            extra=log_extra,
        )
        return state

    # Convert user_id to int
    try:
        user_id = int(user_id_str)
    except ValueError:
        logger.error(
            f"Invalid User ID format '{user_id_str}', cannot finalize processing.",
            extra=log_extra,
        )
        return state

    # Convert assistant_id to UUID
    try:
        assistant_id = UUID(assistant_id_str)
    except ValueError:
        logger.error(
            f"Invalid Assistant ID format '{assistant_id_str}', cannot finalize processing.",
            extra=log_extra,
        )
        return state

    # 1. Update status of summarized messages if any
    if newly_summarized_message_ids:
        # Get latest summary ID first
        latest_summary = None
        try:
            latest_summary = await rest_client.get_user_summary(user_id, assistant_id)
        except Exception as e:
            logger.error(
                f"Error getting latest summary: {str(e)}",
                extra=log_extra,
                exc_info=True,
            )

        if latest_summary and latest_summary.id:
            summary_id = latest_summary.id
            # Update all newly summarized messages to link them to the summary
            success_count = 0
            for msg_id in newly_summarized_message_ids:
                try:
                    update_data = MessageUpdate(
                        status="summarized", summary_id=summary_id
                    )
                    updated = await rest_client.update_message(msg_id, update_data)
                    if updated:
                        success_count += 1
                    else:
                        logger.warning(
                            f"Failed to update message status (ID: {msg_id})",
                            extra=log_extra,
                        )
                except Exception as e:
                    logger.error(
                        f"Error updating message status for ID {msg_id}: {str(e)}",
                        extra=log_extra,
                    )

            logger.info(
                f"Updated {success_count}/{len(newly_summarized_message_ids)} messages with summary_id={summary_id}",
                extra=log_extra,
            )
        else:
            logger.warning(
                "No latest summary found, cannot update message statuses",
                extra=log_extra,
            )

    # 2. Check if initial message needs error status update
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
                    f"Failed to update message status to 'processed' (ID: {initial_message_id})",
                    extra=log_extra,
                )
        except Exception as e:
            logger.error(
                f"Error updating message processed status: {str(e)}", extra=log_extra
            )

    # 3. Perform any additional cleanup or finalization tasks
    # (none needed at the moment)

    # Return the state unchanged - we're just doing side effects here
    return state
