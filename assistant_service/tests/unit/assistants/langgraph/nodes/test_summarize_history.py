# assistant_service/tests/unit/assistants/langgraph/nodes/test_summarize_history.py
import asyncio
import uuid
from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

# Adjust imports for new structure
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
)
from langchain_core.outputs import ChatGeneration, ChatResult


# --- Mock LLM ---
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
        response_content = self.summary_content

        # Check if it's an update prompt (based on the structure from summarize_history_node)
        is_update = any(
            isinstance(m, SystemMessage) and m.content.startswith("Current summary:")
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
def node_mock_summary_llm():  # Rename to avoid conflict with graph conftest
    """Provides a resettable mock LLM instance for node tests."""
    model = MockSummaryChatModel()
    yield model
    model.reset_mock()


# Use mock_rest_client from unit/conftest.py
# @pytest.fixture
# def mock_rest_client():
#     mock = MagicMock()
#     mock.get_user_summary = AsyncMock(return_value=None)
#     mock.create_or_update_user_summary = AsyncMock()
#     mock.get_user_facts = AsyncMock(return_value=[])
#     return mock

TEST_ASSISTANT_UUID = "a1b2c3d4-e5f6-7890-1234-567890abcdef"


# --- Helper to create state ---
def create_mock_state(
    messages: List[BaseMessage],
    user_id: str = "123",
    assistant_id: str = TEST_ASSISTANT_UUID,
    llm_context_size: int = 8192,
) -> AssistantState:
    return AssistantState(
        messages=messages,
        user_id=user_id,
        assistant_id=assistant_id,
        llm_context_size=llm_context_size,
        triggered_event={},
        last_summary_ts=None,  # Node fetches this
        log_extra={"assistant_id": assistant_id},
        dialog_state=None,
    )


# --- Tests ---

pytestmark = pytest.mark.asyncio


async def test_summarize_not_needed_due_to_low_message_count(
    node_mock_summary_llm, mock_rest_client
):
    """Test that summarization node does nothing if not enough messages."""
    messages = [
        HumanMessage(content="hi", id=str(uuid.uuid4())),
        AIMessage(content="hello", id=str(uuid.uuid4())),
    ]
    # Assume MESSAGES_TO_KEEP_TAIL is 5, so 2 messages won't trigger
    mock_state = create_mock_state(messages)

    result = await summarize_history_node(
        mock_state, node_mock_summary_llm, mock_rest_client
    )

    assert result == {"messages": []}  # Expect no changes
    assert node_mock_summary_llm.call_count == 0
    mock_rest_client.get_user_summary.assert_not_awaited()
    mock_rest_client.create_or_update_user_summary.assert_not_awaited()


async def test_summarize_creates_initial_summary(
    node_mock_summary_llm, mock_rest_client
):
    """Test creating the first summary and saving it via REST."""
    msg_ids = [str(uuid.uuid4()) for _ in range(6)]  # 6 messages to trigger summary
    messages = [
        HumanMessage(content="msg 0", id=msg_ids[0]),
        AIMessage(content="msg 1", id=msg_ids[1]),
        HumanMessage(content="msg 2", id=msg_ids[2]),
        AIMessage(content="msg 3", id=msg_ids[3]),
        HumanMessage(content="msg 4", id=msg_ids[4]),
        AIMessage(content="msg 5", id=msg_ids[5]),
    ]
    mock_state = create_mock_state(messages, user_id="123")

    # Configure mocks
    expected_summary = "Initial summary of msg 0."
    node_mock_summary_llm.summary_content = expected_summary
    mock_rest_client.get_user_summary.return_value = None  # No existing summary

    # Act
    result = await summarize_history_node(
        mock_state, node_mock_summary_llm, mock_rest_client
    )

    # Assert
    assert node_mock_summary_llm.call_count == 1
    # Check prompt passed to LLM (should not contain 'Current summary:')
    assert node_mock_summary_llm.last_prompt is not None
    assert not any(
        isinstance(m, SystemMessage) and m.content.startswith("Current summary:")
        for m in node_mock_summary_llm.last_prompt
    )

    assert "messages" in result
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], RemoveMessage)
    assert result["messages"][0].id == msg_ids[0]  # First message removed

    mock_rest_client.get_user_summary.assert_awaited_once_with(
        user_id=123, secretary_id=uuid.UUID(TEST_ASSISTANT_UUID)
    )
    mock_rest_client.create_or_update_user_summary.assert_awaited_once_with(
        user_id=123,
        secretary_id=uuid.UUID(TEST_ASSISTANT_UUID),
        summary_text=expected_summary,
    )


async def test_summarize_updates_existing_summary(
    node_mock_summary_llm, mock_rest_client
):
    """Test updating an existing summary (fetched via REST) and saving via REST."""
    msg_ids = [str(uuid.uuid4()) for _ in range(6)]
    messages = [
        HumanMessage(content="msg 0", id=msg_ids[0]),  # This will be summarized
        AIMessage(content="msg 1", id=msg_ids[1]),
        HumanMessage(content="msg 2", id=msg_ids[2]),
        AIMessage(content="msg 3", id=msg_ids[3]),
        HumanMessage(content="msg 4", id=msg_ids[4]),
        AIMessage(content="msg 5", id=msg_ids[5]),
    ]
    mock_state = create_mock_state(messages, user_id="123")

    # Configure mocks
    old_summary_text = "Previously summarized text."
    new_summary = "Summary based on msg 0."
    node_mock_summary_llm.summary_content = new_summary
    mock_rest_client.get_user_summary.return_value = MagicMock(
        summary_text=old_summary_text
    )

    # Act
    result = await summarize_history_node(
        mock_state, node_mock_summary_llm, mock_rest_client
    )

    # --- Debug Logging ---
    print(f"DEBUG: Result messages: {result.get('messages')}")
    if result.get("messages"):
        print(f"DEBUG: Returned RemoveMessage ID: {result['messages'][0].id}")
    print(f"DEBUG: Expected RemoveMessage ID (msg_ids[0]): {msg_ids[0]}")
    # --- End Debug Logging ---

    # Assert
    assert node_mock_summary_llm.call_count == 1
    # Check prompt passed to LLM (should contain 'Current summary:')
    assert node_mock_summary_llm.last_prompt is not None
    assert any(
        isinstance(m, SystemMessage) and m.content.startswith("Current summary:")
        for m in node_mock_summary_llm.last_prompt
    )
    assert any(
        isinstance(m, SystemMessage) and old_summary_text in m.content
        for m in node_mock_summary_llm.last_prompt
    )

    assert "messages" in result
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], RemoveMessage)
    returned_id = result["messages"][0].id
    expected_id = msg_ids[0]
    assert returned_id == expected_id

    mock_rest_client.get_user_summary.assert_awaited_once_with(
        user_id=123, secretary_id=uuid.UUID(TEST_ASSISTANT_UUID)
    )
    # Expecting the *updated* summary content from the mock LLM
    mock_rest_client.create_or_update_user_summary.assert_awaited_once_with(
        user_id=123,
        secretary_id=uuid.UUID(TEST_ASSISTANT_UUID),
        summary_text=f"Updated: {new_summary}",
    )


async def test_summarize_handles_multiple_messages_to_remove(
    node_mock_summary_llm, mock_rest_client, monkeypatch
):
    """Test scenario where multiple messages need summarization."""
    # Monkeypatch the constant to force summarizing more messages
    monkeypatch.setattr(
        "assistants.langgraph.nodes.summarize_history.MESSAGES_TO_KEEP_TAIL", 2
    )

    msg_ids = [
        str(uuid.uuid4()) for _ in range(4)
    ]  # 4 messages, keep 2 tail -> summarize first 2
    messages = [
        HumanMessage(content="msg 0", id=msg_ids[0]),
        AIMessage(content="msg 1", id=msg_ids[1]),
        HumanMessage(content="msg 2", id=msg_ids[2]),
        AIMessage(content="msg 3", id=msg_ids[3]),
    ]
    mock_state = create_mock_state(messages, user_id="123")

    # Configure mocks
    expected_summary = "Summary of msg 0 and msg 1."
    node_mock_summary_llm.summary_content = expected_summary
    mock_rest_client.get_user_summary.return_value = None  # No existing summary

    # Act
    result = await summarize_history_node(
        mock_state, node_mock_summary_llm, mock_rest_client
    )

    # Assert: LLM called once (batches summary)
    assert node_mock_summary_llm.call_count == 1

    # Assert: Result contains two RemoveMessages
    assert "messages" in result
    assert len(result["messages"]) == 2
    assert all(isinstance(m, RemoveMessage) for m in result["messages"])
    removed_ids = {m.id for m in result["messages"]}
    assert removed_ids == {msg_ids[0], msg_ids[1]}

    # Assert: Summary saved via REST
    mock_rest_client.get_user_summary.assert_awaited_once()
    mock_rest_client.create_or_update_user_summary.assert_awaited_once_with(
        user_id=123,
        secretary_id=uuid.UUID(TEST_ASSISTANT_UUID),
        summary_text=expected_summary,
    )


async def test_summarize_handles_llm_error_gracefully(
    node_mock_summary_llm, mock_rest_client, monkeypatch
):
    """Test that the node raises an error if the LLM call fails."""
    monkeypatch.setattr(
        "assistants.langgraph.nodes.summarize_history.MESSAGES_TO_KEEP_TAIL", 1
    )
    messages = [
        HumanMessage(content="msg 0", id="id0"),
        AIMessage(content="msg 1", id="id1"),
    ]
    mock_state = create_mock_state(messages, user_id="123")

    # Configure mock LLM to raise an error
    llm_error_message = "LLM API failed"
    node_mock_summary_llm.error_to_raise = ValueError(llm_error_message)
    mock_rest_client.get_user_summary.return_value = None

    # Act & Assert: Expect ValueError to be raised
    with pytest.raises(ValueError, match=llm_error_message):
        await summarize_history_node(
            mock_state, node_mock_summary_llm, mock_rest_client
        )

    # Assert: LLM was still called before the error
    assert node_mock_summary_llm.call_count == 1
    # Assert: REST get was attempted, but save was not
    mock_rest_client.get_user_summary.assert_awaited_once()
    mock_rest_client.create_or_update_user_summary.assert_not_awaited()


async def test_summarize_handles_rest_get_error_gracefully(
    node_mock_summary_llm, mock_rest_client, monkeypatch
):
    """Test that the node proceeds without old summary if REST GET fails."""
    monkeypatch.setattr(
        "assistants.langgraph.nodes.summarize_history.MESSAGES_TO_KEEP_TAIL", 1
    )
    messages = [
        HumanMessage(content="msg 0", id="id0"),
        AIMessage(content="msg 1", id="id1"),
    ]
    mock_state = create_mock_state(messages, user_id="123")

    # Configure mocks
    mock_rest_client.get_user_summary.side_effect = Exception("REST GET Failed")
    expected_summary = "Summary without old context."
    node_mock_summary_llm.summary_content = expected_summary

    # Act
    result = await summarize_history_node(
        mock_state, node_mock_summary_llm, mock_rest_client
    )

    # Assert: LLM still called (but without old summary context)
    assert node_mock_summary_llm.call_count == 1
    assert node_mock_summary_llm.last_prompt is not None
    assert not any(
        isinstance(m, SystemMessage) and m.content.startswith("Current summary:")
        for m in node_mock_summary_llm.last_prompt
    )

    # Assert: Message marked for removal
    assert "messages" in result and len(result["messages"]) == 1
    assert isinstance(result["messages"][0], RemoveMessage)
    assert result["messages"][0].id == "id0"

    # Assert: Attempt to save the new summary still happens
    mock_rest_client.get_user_summary.assert_awaited_once()
    mock_rest_client.create_or_update_user_summary.assert_awaited_once_with(
        user_id=123,
        secretary_id=uuid.UUID(TEST_ASSISTANT_UUID),
        summary_text=expected_summary,
    )


async def test_summarize_handles_rest_save_error_gracefully(
    node_mock_summary_llm, mock_rest_client, monkeypatch
):
    """Test that the node completes even if saving the summary via REST fails."""
    monkeypatch.setattr(
        "assistants.langgraph.nodes.summarize_history.MESSAGES_TO_KEEP_TAIL", 1
    )
    messages = [
        HumanMessage(content="msg 0", id="id0"),
        AIMessage(content="msg 1", id="id1"),
    ]
    mock_state = create_mock_state(messages, user_id="123")

    # Configure mocks
    mock_rest_client.get_user_summary.return_value = None
    mock_rest_client.create_or_update_user_summary.side_effect = Exception(
        "REST SAVE Failed"
    )
    node_mock_summary_llm.summary_content = "Summary to be saved."

    # Act
    result = await summarize_history_node(
        mock_state, node_mock_summary_llm, mock_rest_client
    )

    # Assert: LLM was called
    assert node_mock_summary_llm.call_count == 1

    # Assert: Message still marked for removal
    assert "messages" in result and len(result["messages"]) == 1
    assert isinstance(result["messages"][0], RemoveMessage)
    assert result["messages"][0].id == "id0"

    # Assert: REST calls were attempted
    mock_rest_client.get_user_summary.assert_awaited_once()
    mock_rest_client.create_or_update_user_summary.assert_awaited_once()
