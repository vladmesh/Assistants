# assistant_service/tests/assistants/test_langgraph_assistant.py

import asyncio
from datetime import datetime, timezone
from typing import Any, List, Optional
from unittest.mock import AsyncMock, patch

import pytest
from assistants.base_assistant import BaseAssistant

# Imports specific to the class under test
from assistants.langgraph_assistant import AssistantState, LangGraphAssistant
from config import settings
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledGraph
from tools.time_tool import TimeToolWrapper  # Import a real simple tool


# Mock LLM that inherits from BaseChatModel
class MockChatOpenAI(BaseChatModel):
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Synchronous generation (required by BaseChatModel)."""
        last_message = messages[-1]
        content = "Default sync mock response"
        if isinstance(last_message, HumanMessage):
            content = f"Sync mock reply to: {last_message.content}"

        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Asynchronous generation (required by BaseChatModel)."""
        last_message = messages[-1]
        content = "Default async mock response"
        if isinstance(last_message, HumanMessage):
            content = f"Async mock reply to: {last_message.content}"

        # Simulate the structure needed internally by LangGraph/React Agent if necessary
        # Based on previous errors, the agent might return a dict like {'messages': [AIMessage(...)]}
        # However, BaseChatModel._agenerate should return ChatResult.
        # Let's return the standard ChatResult, LangGraph should handle wrapping it.
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        # Simulate some delay if needed
        await asyncio.sleep(0.01)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        """Return type of chat model."""
        return "mock_chat_openai"

    def bind_tools(self, tools):
        # Override if needed, BaseChatModel might have a default
        # For the mock, just return self if this method is called.
        return self


@pytest.fixture
def memory_saver():
    """Fixture for an in-memory checkpointer."""
    return MemorySaver()


@pytest.fixture
def basic_config():
    """Basic assistant configuration."""
    return {
        "model_name": "mock-model",
        "temperature": 0.5,
        "system_prompt": "You are a test assistant.",
        "timeout": 30,
        "api_key": "mock-key",  # Provide a mock key
    }


@pytest.fixture
def time_tool_def():
    """Definition for the time tool."""
    return {
        "tool_type": "time",
        "name": "current_time",
        "description": "Get current time",
    }


@pytest.fixture
@patch("assistants.langgraph_assistant.ChatOpenAI", new_callable=lambda: MockChatOpenAI)
def assistant_instance(mock_chat_openai, memory_saver, basic_config, time_tool_def):
    """Fixture to create an instance of LangGraphAssistant with mocks."""
    # Ensure global settings has a mock key if needed by tool init (WebSearch might need it)
    settings.tavily_api_key = "mock-tavily-key"
    settings.openai_api_key = "mock-global-key"  # Fallback

    instance = LangGraphAssistant(
        assistant_id="test-asst-id",
        name="test_assistant",
        config=basic_config,
        tool_definitions=[time_tool_def],
        checkpointer=memory_saver,
    )
    # Replace the agent runnable's invoke with AsyncMock AFTER initialization
    # This allows us to inspect calls made by the graph node
    instance.agent_runnable = AsyncMock()
    # Set a default return value structure similar to create_react_agent output
    instance.agent_runnable.ainvoke.return_value = {
        "messages": [AIMessage(content="Mock agent response")]
    }
    return instance


@pytest.mark.asyncio
async def test_initialization(assistant_instance, memory_saver, basic_config):
    """Test if the assistant initializes correctly."""
    assert isinstance(assistant_instance, LangGraphAssistant)
    assert isinstance(assistant_instance, BaseAssistant)
    assert assistant_instance.assistant_id == "test-asst-id"
    assert assistant_instance.name == "test_assistant"
    assert assistant_instance.checkpointer == memory_saver
    assert assistant_instance.timeout == basic_config["timeout"]
    assert assistant_instance.system_prompt == basic_config["system_prompt"]
    assert isinstance(assistant_instance.llm, MockChatOpenAI)  # Check instance type
    assert len(assistant_instance.tools) == 1  # Only time tool should be initialized
    assert isinstance(assistant_instance.tools[0], TimeToolWrapper)
    assert hasattr(
        assistant_instance, "agent_runnable"
    )  # Check if agent runnable exists
    assert isinstance(assistant_instance.compiled_graph, CompiledGraph)


@pytest.mark.asyncio
async def test_process_message_stateless(assistant_instance):
    """Test processing a message. Thread ID is now generated internally."""
    assistant_instance.compiled_graph.ainvoke = (
        AsyncMock()
    )  # Mock the overall graph invoke

    # Set a specific return value for the graph mock for this test
    mock_final_state = {
        "messages": [
            HumanMessage(content="Hi"),
            AIMessage(
                content="Hello Stateless!"
            ),  # Changed response slightly for clarity
        ],
        "user_id": "test_user_stateless",
        "dialog_state": ["idle"],
        "last_activity": datetime.now(timezone.utc),
    }
    assistant_instance.compiled_graph.ainvoke.return_value = mock_final_state

    message = HumanMessage(content="Hi")
    user_id = "test_user_stateless"
    # thread_id is no longer passed externally
    # test_thread_id = "thread_explicit_123"

    # Call process_message without thread_id
    response = await assistant_instance.process_message(
        message, user_id  # Removed thread_id=test_thread_id
    )

    # Assert graph was called with the correct config including the internally generated thread_id
    expected_thread_id = f"user_{user_id}"
    assistant_instance.compiled_graph.ainvoke.assert_called_once_with(
        {"messages": [message], "user_id": user_id},
        config={
            "configurable": {"thread_id": expected_thread_id}
        },  # Expect internally generated thread_id
    )

    assert response == "Hello Stateless!"


@pytest.mark.asyncio
async def test_process_message_stateful_memory(assistant_instance, memory_saver):
    """Test processing two messages with the same user_id to check memory
    (thread_id generated internally based on user_id)."""
    user_id = "test_user_stateful"
    # thread_id is generated internally as f"user_{user_id}"
    expected_thread_id = f"user_{user_id}"

    # --- First message ---
    message1 = HumanMessage(content="My name is Alice")

    # Mock the internal agent_runnable response for the first call
    # It should receive system prompt + message1
    # It returns a state including the AI response
    async def first_call_mock(*args, **kwargs):
        call_input = args[0]
        assert isinstance(call_input["messages"][0], SystemMessage)
        assert call_input["messages"][0].content == assistant_instance.system_prompt
        assert call_input["messages"][1].content == message1.content
        return {
            "messages": [AIMessage(content="Hi Alice!")]
        }  # Simulate agent adding its response

    assistant_instance.agent_runnable.ainvoke.side_effect = first_call_mock

    # Call process_message without thread_id
    response1 = await assistant_instance.process_message(
        message1, user_id  # Removed thread_id=thread_id
    )

    # Checkpoint should contain the history now, using the expected thread_id
    checkpoint = await memory_saver.aget(
        config={
            "configurable": {"thread_id": expected_thread_id}
        }  # Use expected_thread_id
    )
    assert checkpoint is not None
    saved_state = AssistantState(**checkpoint["channel_values"])  # Reconstruct state
    # History should contain Human, AI messages (System might be implicit in agent or added later)
    assert len(saved_state["messages"]) >= 2  # At least Human + AI
    assert any(
        isinstance(msg, HumanMessage) and msg.content == "My name is Alice"
        for msg in saved_state["messages"]
    )
    assert any(
        isinstance(msg, AIMessage) and msg.content == "Hi Alice!"
        for msg in saved_state["messages"]
    )
    assert response1 == "Hi Alice!"  # Check response extracted

    # --- Second message ---
    message2 = HumanMessage(content="What is my name?")

    # Mock the internal agent_runnable response for the second call
    # Crucially, it should receive the full history from the checkpointer
    async def second_call_mock(*args, **kwargs):
        call_input = args[0]
        messages_received = call_input["messages"]
        # Check history received by agent runnable
        assert isinstance(
            messages_received[0], SystemMessage
        )  # System prompt prepended by node
        assert messages_received[0].content == assistant_instance.system_prompt
        assert isinstance(messages_received[1], HumanMessage)
        assert messages_received[1].content == "My name is Alice"
        assert isinstance(messages_received[2], AIMessage)
        assert messages_received[2].content == "Hi Alice!"
        assert isinstance(messages_received[3], HumanMessage)  # The new message
        assert messages_received[3].content == "What is my name?"
        return {
            "messages": [AIMessage(content="Your name is Alice.")]
        }  # Simulate agent adding its response

    assistant_instance.agent_runnable.ainvoke.side_effect = second_call_mock

    # Call process_message again for the same user_id (implicitly same thread_id)
    response2 = await assistant_instance.process_message(
        message2, user_id  # Removed thread_id=thread_id
    )

    assert response2 == "Your name is Alice."

    # Verify the final state in the checkpointer
    final_checkpoint = await memory_saver.aget(
        config={"configurable": {"thread_id": expected_thread_id}}
    )
    assert final_checkpoint is not None
    final_state = AssistantState(**final_checkpoint["channel_values"])
    assert len(final_state["messages"]) >= 4  # Should have Human, AI, Human, AI
    assert final_state["messages"][-1].content == "Your name is Alice."
