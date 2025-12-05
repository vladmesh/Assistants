import logging
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from shared_models.api_schemas.message import MessageCreate, MessageUpdate

from assistants.langgraph.state import AssistantState
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)


async def _update_initial_message_status(
    rest_client: RestServiceClient,
    message_id: int | None,
    log_extra: dict,
    status: str = "processed",  # Added status parameter with default
):
    """Helper to update initial message status."""
    if not message_id:  # message_id can be None if save_input_node failed
        logger.debug(
            f"No initial_message_id provided, cannot update status to '{status}'.",
            extra=log_extra,
        )
        return
    try:
        update_data = MessageUpdate(status=status)  # Use the passed status
        updated = await rest_client.update_message(message_id, update_data)
        if updated:
            logger.info(
                "Successfully updated input message "
                f"(ID: {message_id}) status to '{status}'.",
                extra=log_extra,
            )
        else:
            logger.warning(
                "Failed to update input message "
                f"(ID: {message_id}) status to '{status}'. API returned non-true.",
                extra=log_extra,
            )
    except Exception as e:
        logger.error(
            "Error updating input message "
            f"(ID: {message_id}) status to '{status}': {str(e)}",
            extra=log_extra,
            exc_info=True,
        )


async def save_response_node(
    state: AssistantState, rest_client: RestServiceClient
) -> dict[str, Any]:
    # Centralized log_extra for this node
    log_extra = state.get("log_extra", {})
    # Ensure user_id and assistant_id are in log_extra if available in state
    if "user_id" not in log_extra and state.get("user_id"):
        log_extra["user_id"] = state.get("user_id")
    if "assistant_id" not in log_extra and state.get("assistant_id"):
        log_extra["assistant_id"] = state.get("assistant_id")

    logger.info(
        "[save_response_node] Entered: Processing messages for saving to database.",
        extra=log_extra,
    )

    user_id_str = state.get("user_id")
    assistant_id_str = state.get("assistant_id")
    # DB ID of the primary human message for this run, set by save_input_node
    initial_message_db_id: int | None = state.get("initial_message_id")

    if not user_id_str or not assistant_id_str:
        logger.error(
            "User ID or Assistant ID not found in state. Cannot save messages.",
            extra=log_extra,
        )
        # Attempt to update status even if we can't save new messages.
        # Graph reached this point, so mark as error.
        await _update_initial_message_status(
            rest_client, initial_message_db_id, log_extra, status="error"
        )
        return state

    try:
        user_id_int = int(user_id_str)
        assistant_id_uuid = UUID(assistant_id_str)
    except ValueError:
        logger.error(
            (
                f"Invalid User ID '{user_id_str}' "
                f"or Assistant ID '{assistant_id_str}' format."
            ),
            extra=log_extra,
        )
        await _update_initial_message_status(
            rest_client, initial_message_db_id, log_extra, status="error"
        )
        return state

    all_messages_in_state: list[BaseMessage] = state.get("messages", [])
    # The actual input BaseMessage object for this current run/invocation
    current_input_message_obj: BaseMessage | None = state.get("initial_message")

    if not all_messages_in_state:
        logger.warning(
            "No messages found in state ('messages' list is empty). Nothing to save.",
            extra=log_extra,
        )
        # If no messages in state, it's unusual but graph processed up to here.
        # Mark as processed; no specific error in this node, but flow might be flawed.
        await _update_initial_message_status(
            rest_client, initial_message_db_id, log_extra, status="processed"
        )
        return state

    start_saving_from_index = 0
    if current_input_message_obj:
        try:
            # Find the current input message object in the list of all messages.
            # Messages after this one are considered new and generated in this run.
            # load_context_node places it at the end of historical messages.
            start_saving_from_index = (
                all_messages_in_state.index(current_input_message_obj) + 1
            )
            logger.info(
                (
                    "Input message index "
                    f"{start_saving_from_index - 1}; saving from "
                    f"{start_saving_from_index}."
                ),
                extra=log_extra,
            )
        except ValueError:
            # current_input_message_obj (from state.initial_message)
            # is not in state.messages. This indicates a potential
            # inconsistency in state management earlier in the graph.
            logger.error(
                (
                    "Critical: Current input message object ('initial_message') "
                    "NOT FOUND in 'messages' list. Cannot reliably determine which "
                    "messages are new. Will attempt to save only AI and Tool "
                    "messages from the list."
                ),
                extra=log_extra,
            )
            # Fallback: process all messages in the list, but filter by type
            # to only save AI/Tool messages. This avoids re-saving historical
            # HumanMessages but might miss context. Since this is a critical
            # state inconsistency, mark the original message as error.
            await _update_initial_message_status(
                rest_client, initial_message_db_id, log_extra, status="error"
            )
            start_saving_from_index = 0
            # Potentially return state here if we consider this unrecoverable for saving
            # return state
    else:
        # This means state.initial_message was not set or was None.
        logger.error(
            (
                "Critical: 'initial_message' not found in state. Cannot determine "
                "new messages. Will attempt to save only AI and Tool messages "
                "from the list."
            ),
            extra=log_extra,
        )
        # Mark original message as error due to missing critical state component
        await _update_initial_message_status(
            rest_client, initial_message_db_id, log_extra, status="error"
        )
        start_saving_from_index = 0
        # Potentially return state here
        # return state

    # If we returned state in critical error blocks above, the loop won't run.
    # If we proceed, attempt to save what we can.
    for msg_idx in range(start_saving_from_index, len(all_messages_in_state)):
        message_to_save = all_messages_in_state[msg_idx]

        if isinstance(message_to_save, HumanMessage):
            logger.debug(
                (
                    f"Skipping HumanMessage at index {msg_idx} "
                    f"('{str(message_to_save.content)[:50]}...') "
                    "in save_response_node."
                ),
                extra=log_extra,
            )
            continue

        message_payload: MessageCreate | None = None
        role_for_db: str | None = None
        content_for_db: str = ""
        tool_call_id_for_db: str | None = None
        metadata_for_db: dict[str, Any] = {}

        if isinstance(message_to_save, AIMessage):
            role_for_db = "assistant"
            content_for_db = (
                message_to_save.content if message_to_save.content is not None else ""
            )

            if message_to_save.tool_calls:
                tool_calls_data = []
                for tc in message_to_save.tool_calls:
                    tool_calls_data.append(
                        {
                            "name": tc.get("name"),
                            "id": tc.get("id"),
                            "args": tc.get("args"),
                        }
                    )
                metadata_for_db["tool_calls"] = tool_calls_data
                tool_call_id_for_db = None

            message_payload = MessageCreate(
                user_id=user_id_int,
                assistant_id=assistant_id_uuid,
                role=role_for_db,
                content=content_for_db,
                content_type="text",
                status="processed",
                tool_call_id=tool_call_id_for_db,
                meta_data=metadata_for_db if metadata_for_db else None,
                parent_message_id=None,
            )

        elif isinstance(message_to_save, ToolMessage):
            role_for_db = "tool"
            content_for_db = str(message_to_save.content)
            tool_call_id_for_db = message_to_save.tool_call_id

            metadata_for_db["tool_name"] = message_to_save.name
            if message_to_save.additional_kwargs:
                metadata_for_db.update(message_to_save.additional_kwargs)

            message_payload = MessageCreate(
                user_id=user_id_int,
                assistant_id=assistant_id_uuid,
                role=role_for_db,
                content=content_for_db,
                content_type="text",
                status="processed",
                tool_call_id=tool_call_id_for_db,
                meta_data=metadata_for_db if metadata_for_db else None,
                parent_message_id=None,
            )

        if message_payload:
            try:
                logger.info(
                    f"Attempting to save to DB: Role='{message_payload.role}', "
                    f"Content='{str(message_payload.content)[:60]}...', "
                    f"ToolCallID_on_payload='{message_payload.tool_call_id}'",
                    extra=log_extra,
                )
                saved_message_db_record = await rest_client.create_message(
                    message_payload
                )
                if saved_message_db_record and saved_message_db_record.id:
                    logger.info(
                        (
                            "Successfully saved message to DB "
                            f"(DB ID: {saved_message_db_record.id}, "
                            f"Role: {message_payload.role}, "
                            "ToolCallID in DB record: "
                            f"{saved_message_db_record.tool_call_id})"
                        ),
                        extra=log_extra,
                    )
                else:
                    logger.error(
                        (
                            "Failed to save message: No ID returned from REST API "
                            "or save operation failed."
                        ),
                        extra=log_extra,
                    )
            except Exception as e:
                logger.error(
                    f"Error saving message (Role: {message_payload.role}, "
                    f"Content: {str(message_payload.content)[:60]}): {str(e)}",
                    extra=log_extra,
                    exc_info=True,
                )

    # Final status update. Errors above mark status=error; otherwise processed.
    await _update_initial_message_status(
        rest_client, initial_message_db_id, log_extra
    )  # Defaults to "processed"

    return state
