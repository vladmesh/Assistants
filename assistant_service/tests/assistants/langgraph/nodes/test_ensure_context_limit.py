import asyncio
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from assistants.langgraph.constants import HISTORY_SUMMARY_NAME
from assistants.langgraph.nodes.ensure_context_limit import ensure_context_limit_node
from assistants.langgraph.state import AssistantState
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)


# --- Helper Functions/Fixtures ---
def create_message(msg_type, content, name=None, msg_id=None):
    """Helper to create messages with IDs."""
    kwargs = {"content": content, "id": msg_id or str(uuid.uuid4())}
    if name:
        kwargs["name"] = name
    return msg_type(**kwargs)


# --- Tests ---


@pytest.mark.asyncio
async def test_ensure_limit_not_needed():
    """Test that no changes are made if token count is within the limit."""
    messages = [
        create_message(SystemMessage, "Summary", name=HISTORY_SUMMARY_NAME),
        create_message(HumanMessage, "User query"),
        create_message(AIMessage, "AI response"),
    ]
    limit = 1000  # High limit, low token count
    # target = int(limit * 0.9) # TRIM_THRESHOLD_PERCENT is 0.9

    # No need to mock count_tokens anymore
    # mock_count_tokens.return_value = target - 50

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=limit,
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )

    result = await ensure_context_limit_node(mock_state)

    # Expect no messages in the result, as nothing should be changed
    assert result == {"messages": []}
    # Verify count_tokens was called


@pytest.mark.asyncio
async def test_ensure_limit_removes_oldest_messages():
    """Test removing oldest messages (excluding summary and last) to fit the limit."""
    summary_id = str(uuid.uuid4())
    old_msg1_id = str(uuid.uuid4())
    old_msg2_id = str(uuid.uuid4())
    last_msg_id = str(uuid.uuid4())

    # Make old messages very long
    long_content = "Old message content repeated. " * 150

    messages = [
        create_message(
            SystemMessage, "Summary", name=HISTORY_SUMMARY_NAME, msg_id=summary_id
        ),  # Short
        create_message(
            HumanMessage, long_content, msg_id=old_msg1_id
        ),  # Long - To be removed 1st
        create_message(
            AIMessage, long_content, msg_id=old_msg2_id
        ),  # Long - To be removed 2nd
        create_message(
            HumanMessage, "Last msg", msg_id=last_msg_id
        ),  # Short - To be kept
    ]
    limit = 150  # Low limit to force removal of both long messages
    # target = int(limit * 0.9) # 135

    # No need to mock count_tokens
    # initial_call_count = 0
    # def count_side_effect(msgs):
    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=limit,
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )
    result = await ensure_context_limit_node(mock_state)

    assert "messages" in result
    updates = result["messages"]

    # Expect only RemoveMessage instructions
    assert all(isinstance(m, RemoveMessage) for m in updates)
    assert len(updates) == 2

    removed_ids = {m.id for m in updates}
    assert old_msg1_id in removed_ids
    assert old_msg2_id in removed_ids
    assert summary_id not in removed_ids
    assert last_msg_id not in removed_ids


@pytest.mark.asyncio
@patch("assistants.langgraph.nodes.ensure_context_limit._create_truncated_message")
async def test_ensure_limit_removes_and_truncates_summary(mock_create_truncated):
    """Test removing oldest and then truncating summary if still needed."""
    summary_id = str(uuid.uuid4())
    old_msg1_id = str(uuid.uuid4())
    last_msg_id = str(uuid.uuid4())

    # Make summary and old message long
    summary_content = "This is a long summary that needs truncation. " * 150
    old_msg_content = "Old message content repeated. " * 100
    final_truncated_summary_content = "Truncated Summary"

    messages = [
        create_message(
            SystemMessage, summary_content, name=HISTORY_SUMMARY_NAME, msg_id=summary_id
        ),  # Long
        create_message(
            HumanMessage, old_msg_content, msg_id=old_msg1_id
        ),  # Long - To be removed
        create_message(
            HumanMessage, "Last msg", msg_id=last_msg_id
        ),  # Short - To be kept
    ]
    limit = 150  # Low limit
    # target = int(limit * 0.9) # 135

    # No need to mock count_tokens

    # Mock the _create_truncated_message function to return a short summary
    mock_truncated_msg = create_message(
        SystemMessage,
        final_truncated_summary_content,
        name=HISTORY_SUMMARY_NAME,
        msg_id=summary_id,
    )
    mock_create_truncated.return_value = mock_truncated_msg

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=limit,
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )

    result = await ensure_context_limit_node(mock_state)

    assert "messages" in result
    updates = result["messages"]

    # Expect 1 RemoveMessage (old_msg1) and 1 updated SystemMessage (summary)
    assert len(updates) == 2

    remove_msgs = [m for m in updates if isinstance(m, RemoveMessage)]
    assert len(remove_msgs) == 1
    assert remove_msgs[0].id == old_msg1_id

    truncated_summaries = [m for m in updates if isinstance(m, SystemMessage)]
    assert len(truncated_summaries) == 1
    assert truncated_summaries[0].id == summary_id  # ID should be preserved
    assert truncated_summaries[0].name == HISTORY_SUMMARY_NAME
    assert truncated_summaries[0].content == final_truncated_summary_content

    # Verify _create_truncated_message was called for the summary
    mock_create_truncated.assert_called_once()
    # Check the arguments passed to _create_truncated_message (optional, but good practice)
    call_args, _ = mock_create_truncated.call_args
    original_msg_passed = call_args[0]
    truncated_content_passed = call_args[1]
    assert original_msg_passed.id == summary_id
    assert truncated_content_passed.endswith("...")  # Check that ellipsis was added


@pytest.mark.asyncio
@patch("assistants.langgraph.nodes.ensure_context_limit._create_truncated_message")
async def test_ensure_limit_removes_truncates_summary_and_last(mock_create_truncated):
    """Test removing oldest, truncating summary, and truncating last message."""
    summary_id = str(uuid.uuid4())
    old_msg1_id = str(uuid.uuid4())
    last_msg_id = str(uuid.uuid4())

    # Make all messages long initially
    summary_content = "Long summary content repeated. " * 100
    old_msg_content = "Old message content repeated. " * 100
    last_msg_content = (
        "Very long last message that also needs truncation repeated. " * 150
    )
    final_truncated_summary_content = "Trunc S"
    final_truncated_last_content = "Trunc L"

    messages = [
        create_message(
            SystemMessage, summary_content, name=HISTORY_SUMMARY_NAME, msg_id=summary_id
        ),  # Long
        create_message(
            HumanMessage, old_msg_content, msg_id=old_msg1_id
        ),  # Long - Remove
        create_message(
            HumanMessage, last_msg_content, msg_id=last_msg_id
        ),  # Very Long - Keep and truncate
    ]
    limit = 150  # Low limit
    # target = int(limit * 0.9) # 135

    # No need to mock count_tokens

    # Mock _create_truncated_message responses to return short versions
    mock_truncated_summary = create_message(
        SystemMessage,
        final_truncated_summary_content,
        name=HISTORY_SUMMARY_NAME,
        msg_id=summary_id,
    )
    mock_truncated_last = create_message(
        HumanMessage, final_truncated_last_content, msg_id=last_msg_id
    )

    # Define a side_effect function to handle multiple calls correctly
    def create_truncated_side_effect(original_message, truncated_content):
        if (
            isinstance(original_message, SystemMessage)
            and original_message.name == HISTORY_SUMMARY_NAME
        ):
            # Return the pre-defined truncated summary content but with the original ID
            return create_message(
                SystemMessage,
                final_truncated_summary_content,
                name=HISTORY_SUMMARY_NAME,
                msg_id=original_message.id,
            )
        elif isinstance(original_message, HumanMessage):
            # Return the pre-defined truncated last message content with the original ID
            return create_message(
                HumanMessage, final_truncated_last_content, msg_id=original_message.id
            )
        else:
            # Fail test if unexpected type is passed
            pytest.fail(
                f"Unexpected message type passed to mock _create_truncated_message: {type(original_message)}"
            )

    mock_create_truncated.side_effect = create_truncated_side_effect

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=limit,
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )

    result = await ensure_context_limit_node(mock_state)

    assert "messages" in result
    updates = result["messages"]

    # Expect 1 RemoveMessage (old_msg1), 1 truncated SystemMessage (summary), 1 truncated HumanMessage (last)
    assert len(updates) == 3

    remove_msgs = [m for m in updates if isinstance(m, RemoveMessage)]
    assert len(remove_msgs) == 1
    assert remove_msgs[0].id == old_msg1_id

    truncated_summaries = [m for m in updates if isinstance(m, SystemMessage)]
    assert len(truncated_summaries) == 1
    assert truncated_summaries[0].id == summary_id
    assert truncated_summaries[0].content == final_truncated_summary_content

    truncated_last_msgs = [
        m for m in updates if isinstance(m, HumanMessage)
    ]  # Check specific type of last message
    assert len(truncated_last_msgs) == 1
    assert truncated_last_msgs[0].id == last_msg_id
    assert truncated_last_msgs[0].content == final_truncated_last_content

    # Verify _create_truncated_message was called twice
    # assert mock_create_truncated.call_count == 2
    # Check args for first call (summary)
    # assert mock_create_truncated.call_args_list[0][0][0].id == summary_id
    # Check args for second call (last message)
    # assert mock_create_truncated.call_args_list[1][0][0].id == last_msg_id


# TODO: Add tests for edge cases (e.g., no summary, truncation fails due to MIN_CONTENT_LEN)

# TODO: Add more tests
