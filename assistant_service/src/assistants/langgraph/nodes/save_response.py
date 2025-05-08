import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from assistants.langgraph.state import AssistantState
from langchain_core.messages import AIMessage, BaseMessage
from services.rest_service import RestServiceClient

from shared_models.api_schemas.message import MessageCreate, MessageUpdate

logger = logging.getLogger(__name__)


async def save_response_node(
    state: AssistantState, rest_client: RestServiceClient
) -> Dict[str, Any]:
    """
    Saves the assistant's response to the database.
    The response should be the last message in the state.messages sequence.
    Also updates the status of the input message to 'processed'.
    """
    logger.info("[save_response_node] Saving assistant response to database")

    # Extract necessary IDs
    user_id_str = state.get("user_id", "")
    assistant_id_str = state.get("assistant_id", "")
    initial_message_id = state.get("initial_message_id")
    log_extra = state.get("log_extra", {})

    # Input validation
    if not user_id_str or not assistant_id_str:
        logger.error(
            "User ID or Assistant ID not found in state, cannot save response.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Get messages
    messages = state.get("messages", [])
    if not messages:
        logger.warning(
            "No messages in state, no response to save.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Get the last message as the response
    # This assumes the assistant's response is always the last in the sequence
    response_message = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            response_message = msg
            break

    if not response_message:
        logger.warning(
            "No assistant message found in state, nothing to save.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Convert user_id to int
    try:
        user_id = int(user_id_str)
    except ValueError:
        logger.error(
            f"Invalid User ID format '{user_id_str}', cannot save response.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Convert assistant_id to UUID
    try:
        assistant_id = UUID(assistant_id_str)
    except ValueError:
        logger.error(
            f"Invalid Assistant ID format '{assistant_id_str}', cannot save response.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Prepare response data
    response_data = MessageCreate(
        user_id=user_id,
        assistant_id=assistant_id,
        role="assistant",
        content=response_message.content,
        content_type="text",  # Default
        status="processed",  # Responses are already processed
        tool_call_id=None,  # Will be set later if needed
        metadata={},  # Will be filled if needed
    )

    # Special handling for tool call messages
    if hasattr(response_message, "tool_calls") and response_message.tool_calls:
        # Handle tool calls in the response
        # This is a simplified approach - may need to be adjusted
        tool_calls_data = []
        for tool_call in response_message.tool_calls:
            if hasattr(tool_call, "id"):
                response_data.tool_call_id = (
                    tool_call.id
                )  # Use the first tool call ID for now
            tool_calls_data.append(
                {
                    "name": getattr(tool_call, "name", None),
                    "id": getattr(tool_call, "id", None),
                    "args": getattr(tool_call, "args", {}),
                }
            )

        if tool_calls_data:
            response_data.metadata = {"tool_calls": tool_calls_data}

    # 1. Save response to database
    response_id = None
    try:
        saved_response = await rest_client.create_message(response_data)
        if saved_response and saved_response.id:
            response_id = saved_response.id
            logger.info(
                f"Successfully saved assistant response (ID: {saved_response.id})",
                extra=log_extra,
            )
        else:
            logger.error(
                "Failed to save response: No ID returned from API", extra=log_extra
            )
    except Exception as e:
        logger.error(
            f"Error saving assistant response: {str(e)}", extra=log_extra, exc_info=True
        )

    # 2. Update input message status to 'processed' if we have its ID
    if initial_message_id:
        try:
            update_data = MessageUpdate(status="processed")
            updated = await rest_client.update_message(initial_message_id, update_data)
            if updated:
                logger.info(
                    f"Successfully updated input message status (ID: {initial_message_id})",
                    extra=log_extra,
                )
            else:
                logger.warning(
                    f"Failed to update input message status (ID: {initial_message_id})",
                    extra=log_extra,
                )
        except Exception as e:
            logger.error(
                f"Error updating input message status: {str(e)}",
                extra=log_extra,
                exc_info=True,
            )

    # No need to update state here as we're at the end of processing
    return state
