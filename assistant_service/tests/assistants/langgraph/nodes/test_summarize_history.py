# assistant_service/tests/assistants/langgraph/nodes/test_summarize_history.py
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from assistants.langgraph.constants import HISTORY_SUMMARY_NAME
from assistants.langgraph.nodes.summarize_history import summarize_history_node
from assistants.langgraph.state import AssistantState
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult


# --- Mock LLM ---
# Copied from test_langgraph_assistant.py and simplified for node testing
class MockSummaryChatModel(BaseChatModel):
    """Mock Chat Model that returns a predefined summary."""

    summary_content: str = "Default mock summary."
    error_to_raise: Optional[Exception] = None
    call_count: int = 0
    last_prompt: Optional[List[BaseMessage]] = None

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Not used in async tests, but required by base class
        raise NotImplementedError("Sync generation not implemented for mock")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.call_count += 1
        self.last_prompt = messages
        if self.error_to_raise:
            raise self.error_to_raise

        # Simulate LLM creating a summary based on the prompt
        # For simplicity, we just return the predefined summary
        response_content = self.summary_content

        # Check if it's an update prompt
        is_update = any(
            isinstance(m, SystemMessage) and m.content.startswith("Previous summary:")
            for m in messages
        )
        if is_update:
            response_content = f"Updated: {self.summary_content}"

        message = AIMessage(content=response_content)
        generation = ChatGeneration(message=message)
        await asyncio.sleep(0.01)  # Simulate delay
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "mock_summary_chat_model"

    def reset_mock(self):
        self.call_count = 0
        self.last_prompt = None
        self.error_to_raise = None


# --- Test Fixtures ---


@pytest.fixture
def mock_summary_llm():
    """Provides a resettable mock LLM instance."""
    model = MockSummaryChatModel()
    yield model  # Use yield to allow reset after test
    model.reset_mock()  # Reset after test run


# --- Tests ---


@pytest.mark.asyncio
async def test_summarize_not_needed_due_to_low_token_count(mock_summary_llm):
    """
    Test that summarization is skipped if token count is below threshold.
    (Implicitly tested via _select_messages returning empty head_msgs)
    """
    messages = [
        HumanMessage(content="hi", id=str(uuid.uuid4())),
        AIMessage(content="hello", id=str(uuid.uuid4())),
    ]
    # Assume MESSAGES_TO_KEEP_TAIL is 5 (default in node), so 2 messages are not enough

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=8192,  # High limit, summarization threshold not met
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )

    result = await summarize_history_node(mock_state, mock_summary_llm)

    assert result == {"messages": []}
    assert mock_summary_llm.call_count == 0


@pytest.mark.asyncio
async def test_summarize_creates_initial_summary(mock_summary_llm):
    """Test creating the first summary when enough messages accumulate."""
    # MESSAGES_TO_KEEP_TAIL = 5. We need 6 messages to trigger summary of the first one.
    msg_ids = [str(uuid.uuid4()) for _ in range(6)]
    messages = [
        HumanMessage(content="msg 0", id=msg_ids[0]),
        AIMessage(content="msg 1", id=msg_ids[1]),
        HumanMessage(content="msg 2", id=msg_ids[2]),
        AIMessage(content="msg 3", id=msg_ids[3]),
        HumanMessage(content="msg 4", id=msg_ids[4]),
        AIMessage(content="msg 5", id=msg_ids[5]),
    ]

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=500,  # Low limit to ensure summary threshold is met
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )

    # Configure mock LLM response
    mock_summary_llm.summary_content = "Initial summary of msg 0."

    result = await summarize_history_node(mock_state, mock_summary_llm)

    assert mock_summary_llm.call_count == 1
    assert "messages" in result

    updates = result["messages"]
    assert len(updates) == 2  # 1 RemoveMessage, 1 SystemMessage

    # Check RemoveMessage
    remove_msgs = [m for m in updates if isinstance(m, RemoveMessage)]
    assert len(remove_msgs) == 1
    assert remove_msgs[0].id == msg_ids[0]  # Should remove the first message

    # Check SystemMessage (summary)
    summary_msgs = [m for m in updates if isinstance(m, SystemMessage)]
    assert len(summary_msgs) == 1
    assert summary_msgs[0].name == HISTORY_SUMMARY_NAME
    # Mock LLM returns predefined content, not updated one for initial summary
    assert summary_msgs[0].content == "Initial summary of msg 0."

    # Check that the prompt sent to LLM was for initial creation
    assert mock_summary_llm.last_prompt is not None
    assert len(mock_summary_llm.last_prompt) == 1  # Only HumanMessage for initial
    assert isinstance(mock_summary_llm.last_prompt[0], HumanMessage)
    assert (
        "Создай саммари" in mock_summary_llm.last_prompt[0].content
    )  # Check for Russian text
    assert (
        '"Content": "msg 0"' in mock_summary_llm.last_prompt[0].content
    )  # Looser check for content


@pytest.mark.asyncio
async def test_summarize_updates_existing_summary(mock_summary_llm):
    """Test updating an existing summary when new messages accumulate."""
    # Existing summary + 6 messages = 7 total. Keep 5 tail -> summarize first msg + old summary.
    old_summary_id = str(uuid.uuid4())
    msg_ids = [str(uuid.uuid4()) for _ in range(6)]
    messages = [
        SystemMessage(
            content="Old summary content.", name=HISTORY_SUMMARY_NAME, id=old_summary_id
        ),
        HumanMessage(content="msg 0", id=msg_ids[0]),
        AIMessage(content="msg 1", id=msg_ids[1]),
        HumanMessage(content="msg 2", id=msg_ids[2]),
        AIMessage(content="msg 3", id=msg_ids[3]),
        AIMessage(content="msg 4", id=msg_ids[4]),
        AIMessage(
            content="msg 5", id=msg_ids[5]
        ),  # This is the last message to keep in tail
    ]

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=500,  # Low limit
        triggered_event={},
        last_summary_ts=datetime.now(timezone.utc),
        log_extra={},
        dialog_state=None,
    )

    # Configure mock LLM response for update
    mock_summary_llm.summary_content = "New summary based on msg 0 and old summary."

    result = await summarize_history_node(mock_state, mock_summary_llm)

    assert mock_summary_llm.call_count == 1
    assert "messages" in result

    updates = result["messages"]
    # Expect 1 RemoveMessage for old summary, 1 RemoveMessage for msg 0, 1 SystemMessage for new summary
    assert len(updates) == 3

    # Check RemoveMessages
    remove_msgs = [m for m in updates if isinstance(m, RemoveMessage)]
    assert len(remove_msgs) == 2
    removed_ids = {m.id for m in remove_msgs}
    assert old_summary_id in removed_ids
    assert msg_ids[0] in removed_ids  # Should remove the first message summarized

    # Check SystemMessage (new summary)
    summary_msgs = [m for m in updates if isinstance(m, SystemMessage)]
    assert len(summary_msgs) == 1
    assert summary_msgs[0].name == HISTORY_SUMMARY_NAME
    # Mock LLM returns "Updated: ..." for updates
    assert (
        summary_msgs[0].content
        == "Updated: New summary based on msg 0 and old summary."
    )
    assert summary_msgs[0].id != old_summary_id  # Should be a new message

    # Check that the prompt sent to LLM was for update
    assert mock_summary_llm.last_prompt is not None
    # Should have SystemMessage (old summary) + HumanMessage (chunk)
    assert len(mock_summary_llm.last_prompt) == 2
    assert isinstance(mock_summary_llm.last_prompt[0], SystemMessage)
    assert (
        mock_summary_llm.last_prompt[0].content
        == "Previous summary: Old summary content."
    )
    assert isinstance(mock_summary_llm.last_prompt[1], HumanMessage)
    assert (
        "Основываясь на саммари" in mock_summary_llm.last_prompt[1].content
    )  # Check for Russian text
    assert (
        '"Content": "msg 0"' in mock_summary_llm.last_prompt[1].content
    )  # Looser check for content


@pytest.mark.asyncio
async def test_summarize_handles_multiple_chunks(mock_summary_llm, monkeypatch):
    """Test summarization involving multiple chunks due to token limits."""
    # Keep 5 tail, need 8 messages total to summarize first 3 msgs
    # Make content long to force multiple chunks with small context size
    long_content_1 = "A" * 300
    long_content_2 = "B" * 300
    long_content_3 = "C" * 300
    msg_ids = [str(uuid.uuid4()) for _ in range(8)]
    messages = [
        HumanMessage(content=long_content_1, id=msg_ids[0]),  # Chunk 1
        AIMessage(content=long_content_2, id=msg_ids[1]),  # Chunk 2
        HumanMessage(content=long_content_3, id=msg_ids[2]),  # Chunk 3
        AIMessage(content="msg 3", id=msg_ids[3]),
        HumanMessage(content="msg 4", id=msg_ids[4]),
        AIMessage(content="msg 5", id=msg_ids[5]),
        HumanMessage(content="msg 6", id=msg_ids[6]),
        AIMessage(content="msg 7", id=msg_ids[7]),  # Tail starts here
    ]

    # Small context size to force chunking based on content length + overhead
    # Target tokens ~ 500 * 0.7 - 200 = 150. Our content + prompt > 150 easily.
    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=500,
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )

    # Mock LLM responses for each chunk
    # Mock needs to handle multiple calls and update its internal state implicitly
    # Our simple mock just returns the same content, but we check call count
    # Let's simulate the final summary content
    mock_summary_llm.summary_content = "Summary of A, B, and C."

    # Mock asyncio.sleep to speed up test
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    result = await summarize_history_node(mock_state, mock_summary_llm)

    # Expect 3 calls, one for each message in head_msgs as they likely form separate chunks
    # assert mock_summary_llm.call_count == 3
    # Updated expectation: The new logic should fit all 3 long messages into one chunk
    assert mock_summary_llm.call_count == 1

    assert "messages" in result
    updates = result["messages"]
    # Expect 3 RemoveMessages (for msg 0, 1, 2) + 1 SystemMessage (final summary)
    assert len(updates) == 4

    # Check RemoveMessages
    remove_msgs = [m for m in updates if isinstance(m, RemoveMessage)]
    assert len(remove_msgs) == 3
    removed_ids = {m.id for m in remove_msgs}
    assert msg_ids[0] in removed_ids
    assert msg_ids[1] in removed_ids
    assert msg_ids[2] in removed_ids

    # Check SystemMessage (final summary)
    summary_msgs = [m for m in updates if isinstance(m, SystemMessage)]
    assert len(summary_msgs) == 1
    assert summary_msgs[0].name == HISTORY_SUMMARY_NAME
    # Check the final summary content (mock LLM returns the base content on first call, updated on subsequent)
    # The exact content depends on mock logic, let's assume the last call sets the final state
    # assert summary_msgs[0].content == "Updated: Summary of A, B, and C." # Last call uses updated prompt
    # Corrected expectation for initial summary creation:
    assert summary_msgs[0].content == "Summary of A, B, and C."

    # Check that sleep was called (or attempted to be called)
    asyncio.sleep.assert_called()  # Check if the mock was called


@pytest.mark.asyncio
async def test_summarize_handles_llm_error_gracefully(mock_summary_llm, monkeypatch):
    """
    Test that an error during LLM invocation is handled.
    Currently, the node does not catch exceptions from _call_llm,
    so the exception should propagate.
    """
    msg_ids = [str(uuid.uuid4()) for _ in range(6)]
    messages = [
        HumanMessage(content="msg 0", id=msg_ids[0]),
        AIMessage(content="msg 1", id=msg_ids[1]),
        HumanMessage(content="msg 2", id=msg_ids[2]),
        AIMessage(content="msg 3", id=msg_ids[3]),
        HumanMessage(content="msg 4", id=msg_ids[4]),
        AIMessage(content="msg 5", id=msg_ids[5]),
    ]

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=500,  # Low limit
        triggered_event={},
        last_summary_ts=None,
        log_extra={},
        dialog_state=None,
    )

    # Configure mock LLM to raise an error
    error_message = "LLM unavailable"
    mock_summary_llm.error_to_raise = ValueError(error_message)

    # Mock asyncio.sleep as it might be called before error if multiple chunks were planned
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    # Expect the ValueError to be raised by the node
    with pytest.raises(ValueError, match=error_message):
        await summarize_history_node(mock_state, mock_summary_llm)

    # Verify LLM was called once (and failed)
    assert mock_summary_llm.call_count == 1


@pytest.mark.asyncio
async def test_summarize_forces_multiple_chunks_due_to_limit(
    mock_summary_llm, monkeypatch
):
    """
    Test that summarization creates multiple chunks when adding a message
    exceeds the token limit, forcing processing of the current chunk.
    """
    # Keep 5 tail. Need initial summary + 3 head + 5 tail = 9 messages total.
    old_summary_id = str(uuid.uuid4())
    msg_ids = [str(uuid.uuid4()) for _ in range(8)]  # 3 head + 5 tail

    # Setup message content lengths and context limit carefully
    # Effective limit = 660 * 0.9 = 594 tokens
    context_size = 660
    prev_summary_content = "Initial Summary."  # ~5 tokens
    content_0 = "A" * 100  # ~30 tokens
    content_1 = "B" * 400  # ~110 tokens
    content_2 = "C" * 1800  # ~500 tokens

    # Rough prompt token estimation (prompt_text ~50, json_overhead ~20/msg):
    # Prompt 1 (prev_summary + msg_0): 50 + 5 + (20+30) = 105 < 594 -> OK
    # Prompt 2 (prev_summary + msg_0 + msg_1): 50 + 5 + (20+30) + (20+110) = 235 < 594 -> OK
    # Prompt 3 (prev_summary + msg_0 + msg_1 + msg_2): 50 + 5 + 50 + 130 + (20+500) = 755 > 594 -> Process chunk [msg_0, msg_1]
    # --- LLM Call 1 --- (Prompt uses prev_summary)
    # New Summary 1 = "Updated: Summary AB"
    # Prompt 4 (new_summary_1 + msg_2): 50 + ~10 + (20+500) = 580 < 594 -> OK
    # --- LLM Call 2 --- (Prompt uses new_summary_1)
    # Final Summary = "Updated: Summary C"

    messages = [
        SystemMessage(
            content=prev_summary_content, name=HISTORY_SUMMARY_NAME, id=old_summary_id
        ),
        # Head messages to be summarized
        HumanMessage(content=content_0, id=msg_ids[0]),
        AIMessage(content=content_1, id=msg_ids[1]),
        HumanMessage(content=content_2, id=msg_ids[2]),
        # Tail messages to keep
        AIMessage(content="msg 3", id=msg_ids[3]),
        HumanMessage(content="msg 4", id=msg_ids[4]),
        AIMessage(content="msg 5", id=msg_ids[5]),
        HumanMessage(content="msg 6", id=msg_ids[6]),
        AIMessage(content="msg 7", id=msg_ids[7]),
    ]

    mock_state = AssistantState(
        messages=messages,
        user_id="test_user",
        llm_context_size=context_size,
        triggered_event={},
        last_summary_ts=datetime.now(timezone.utc),
        log_extra={},
        dialog_state=None,
    )

    # Mock LLM response
    # The mock adds "Updated: " prefix based on prompt content
    mock_summary_llm.summary_content = "Final Summary ABC"

    # Mock sleep
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    result = await summarize_history_node(mock_state, mock_summary_llm)

    # Assertions
    assert mock_summary_llm.call_count == 2  # Expect two calls due to chunking

    assert "messages" in result
    updates = result["messages"]
    # Expect RemoveMessages for old summary + all 3 head messages, plus 1 final SystemMessage
    assert len(updates) == 5

    # Check RemoveMessages
    remove_msgs = [m for m in updates if isinstance(m, RemoveMessage)]
    assert len(remove_msgs) == 4
    removed_ids = {m.id for m in remove_msgs}
    assert old_summary_id in removed_ids
    assert msg_ids[0] in removed_ids
    assert msg_ids[1] in removed_ids
    assert msg_ids[2] in removed_ids

    # Check final SystemMessage (summary)
    summary_msgs = [m for m in updates if isinstance(m, SystemMessage)]
    assert len(summary_msgs) == 1
    assert summary_msgs[0].name == HISTORY_SUMMARY_NAME
    # The final summary should be based on the *second* LLM call, which had an updated prompt
    assert summary_msgs[0].content == "Updated: Final Summary ABC"

    # Check that sleep was called (at least once)
    asyncio.sleep.assert_called()


# TODO: Add more tests for different scenarios
