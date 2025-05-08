import logging
from typing import Any, Dict, Optional
from uuid import UUID

from assistants.langgraph.state import AssistantState
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from services.rest_service import RestServiceClient

from shared_models.api_schemas.message import MessageCreate

logger = logging.getLogger(__name__)


async def save_input_message_node(
    state: AssistantState, rest_client: RestServiceClient
) -> Dict[str, Any]:
    """
    Saves the input message from the user to the database.
    The input message should be the first message in the state.messages sequence.
    Updates the state with the message ID for later reference.
    """
    logger.info("[save_input_message_node] Saving input message to database")

    # Extract necessary IDs
    user_id_str = state.get("user_id", "")
    assistant_id_str = state.get("assistant_id", "")
    log_extra = state.get("log_extra", {})

    # Input validation
    if not user_id_str or not assistant_id_str:
        logger.error(
            "User ID or Assistant ID not found in state, cannot save message.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Get current message
    messages = state.get("messages", [])
    if not messages:
        logger.warning(
            "No messages in state, nothing to save.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    input_message = messages[0]

    # Convert user_id to int
    try:
        user_id = int(user_id_str)
    except ValueError:
        logger.error(
            f"Invalid User ID format '{user_id_str}', cannot save message.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Convert assistant_id to UUID
    try:
        assistant_id = UUID(assistant_id_str)
    except ValueError:
        logger.error(
            f"Invalid Assistant ID format '{assistant_id_str}', cannot save message.",
            extra=log_extra,
        )
        return state  # Return state unchanged

    # Map LangChain message type to role
    role = _get_role_from_message(input_message)

    # Prepare message data
    message_data = MessageCreate(
        user_id=user_id,
        assistant_id=assistant_id,
        role=role,
        content=input_message.content,
        content_type="text",  # Default
        status="pending_processing",  # Initial status
        tool_call_id=None,  # Will be set later if needed
        metadata={},  # Will be filled if needed
    )

    # Special handling for tool messages
    if hasattr(input_message, "tool_call_id") and input_message.tool_call_id:
        message_data.tool_call_id = input_message.tool_call_id
        # Add any tool-specific metadata if needed

    # Save message to database
    try:
        saved_message = await rest_client.create_message(message_data)
        if saved_message and saved_message.id:
            logger.info(
                f"Successfully saved input message (ID: {saved_message.id}, Role: {role})",
                extra=log_extra,
            )
            # Return updated state with the saved message ID
            return {"initial_message_id": saved_message.id}
        else:
            logger.error(
                "Failed to save message: No ID returned from API", extra=log_extra
            )
    except Exception as e:
        logger.error(
            f"Error saving input message: {str(e)}", extra=log_extra, exc_info=True
        )

    # If we get here, something went wrong
    return state  # Return state unchanged


def _get_role_from_message(message: BaseMessage) -> str:
    """Maps a LangChain message type to a database role."""
    if isinstance(message, HumanMessage):
        return "human"
    elif isinstance(message, AIMessage):
        return "assistant"
    elif isinstance(message, ToolMessage):
        # Distinguish between tool request and response based on message details
        # This might need adjustment based on your specific implementation
        return "tool_response"
    else:
        # Default fallback
        return "human"
