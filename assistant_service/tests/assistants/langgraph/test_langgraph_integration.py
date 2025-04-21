import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from assistants.langgraph.constants import HISTORY_SUMMARY_NAME
from assistants.langgraph.graph_builder import build_full_graph
from assistants.langgraph.langgraph_assistant import LangGraphAssistant
from assistants.langgraph.state import AssistantState
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)


# --- Mock Tools ---


@tool
def echo_tool(input_str: str) -> str:
    """Echoes the input string."""
    logger.info(f"[echo_tool] CALLED with input: '{input_str}'")
    return f"Echo: {input_str}"


mock_tools = [echo_tool]

# --- Mock LLMs ---

# Mock for the main assistant LLM
mock_main_llm = AsyncMock()

# Mock for the summary LLM
mock_summary_llm = AsyncMock()


# --- Fixtures ---


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test to ensure isolation."""
    mock_main_llm.reset_mock()
    mock_summary_llm.reset_mock()
    # Reset side_effect if it was set
    mock_main_llm.side_effect = None


@pytest.fixture
def config():
    """Provides a standard config for invoking the graph."""
    thread_id = str(uuid.uuid4())
    return {"configurable": {"thread_id": thread_id}}


@pytest.fixture
def compiled_graph_factory():
    """Factory fixture to build and compile the graph with mocks and configurable context size."""

    def _factory(llm_context_size: int = 8192):  # Default high limit
        # Mock the assistant node function directly for simplicity in integration tests
        # We'll control its output via mock_main_llm within the tests
        async def mock_run_node_fn(state: AssistantState) -> Dict[str, Any]:
            # Log incoming message types
            incoming_messages = state.get("messages", [])
            incoming_types = [type(m).__name__ for m in incoming_messages]
            logger.info(
                f"[mock_run_node_fn] ENTERED. Incoming message types: {incoming_types}"
            )

            # Simulate LLM call using the mock
            response: BaseMessage = await mock_main_llm(state["messages"])
            # Ensure state always contains llm_context_size for the node
            current_state_dict = dict(state)
            current_state_dict["llm_context_size"] = llm_context_size
            return {"messages": [response]}

        checkpointer = MemorySaver()
        # Ensure the graph builder receives the summary LLM
        graph = build_full_graph(
            run_node_fn=mock_run_node_fn,
            tools=mock_tools,
            checkpointer=checkpointer,
            summary_llm=mock_summary_llm,
            # Pass context size to builder if needed, though nodes primarily get it from state
        )
        return graph

    return _factory


@pytest.fixture
def compiled_graph(compiled_graph_factory):
    """Provides a default compiled graph using the factory."""
    return compiled_graph_factory()  # Use default context size


# --- Tests ---


@pytest.mark.asyncio
async def test_simple_conversation(compiled_graph, config):
    """Test a simple user query and AI response without tools or limits."""
    user_message = HumanMessage(content="Hello there!", id=str(uuid.uuid4()))
    ai_response_content = "Hi! How can I help you today?"
    expected_ai_response = AIMessage(content=ai_response_content, id=str(uuid.uuid4()))

    # Configure the main LLM mock to return the expected AI response
    mock_main_llm.return_value = expected_ai_response

    # Invoke the graph
    final_state = await compiled_graph.ainvoke(
        {"messages": [user_message]}, config=config
    )

    # Assertions
    assert "messages" in final_state
    final_messages = final_state["messages"]

    # Should contain initial user message and the final AI response
    assert len(final_messages) == 2
    assert final_messages[0] == user_message
    assert final_messages[1].content == ai_response_content
    assert isinstance(final_messages[1], AIMessage)

    # Verify the main LLM was called once with the user message
    mock_main_llm.assert_called_once()
    call_args, _ = mock_main_llm.call_args
    assert call_args[0] == [user_message]

    # Verify summary LLM was NOT called
    mock_summary_llm.assert_not_called()


@pytest.mark.asyncio
async def test_conversation_with_tool_call(compiled_graph, config):
    """Test a conversation involving a tool call and response."""
    user_message_content = "Please echo this: Hello Tool!"
    user_message = HumanMessage(content=user_message_content, id=str(uuid.uuid4()))
    tool_input = "Hello Tool!"
    tool_output = f"Echo: {tool_input}"
    final_ai_response_content = f"Okay, I echoed it: {tool_output}"

    # --- Mock LLM Responses ---
    # 1. LLM decides to call the tool
    tool_call_id = "tool_call_abc"
    ai_message_with_tool_call = AIMessage(
        content="",
        tool_calls=[
            ToolCall(
                name=echo_tool.name, args={"input_str": tool_input}, id=tool_call_id
            )
        ],
        id=str(uuid.uuid4()),
    )
    # 2. LLM responds after getting the tool result
    final_ai_response = AIMessage(
        content=final_ai_response_content, id=str(uuid.uuid4())
    )

    mock_main_llm.side_effect = [
        ai_message_with_tool_call,
        final_ai_response,
    ]

    # --- Invoke Graph ---
    final_state = await compiled_graph.ainvoke(
        {"messages": [user_message]}, config=config
    )

    # --- Assertions ---
    assert "messages" in final_state
    final_messages = final_state["messages"]

    # Expected sequence: User -> AI (Tool Call) -> Tool Result -> AI (Final Answer)
    assert len(final_messages) == 4

    # 1. User Message
    assert final_messages[0] == user_message

    # 2. AI Message with Tool Call
    assert isinstance(final_messages[1], AIMessage)
    assert final_messages[1].content == ""
    assert len(final_messages[1].tool_calls) == 1
    # Check the dictionary directly
    assert final_messages[1].tool_calls[0]["name"] == echo_tool.name
    assert final_messages[1].tool_calls[0]["args"] == {"input_str": tool_input}
    assert final_messages[1].tool_calls[0]["id"] == tool_call_id

    # 3. Tool Message with Result
    assert isinstance(final_messages[2], ToolMessage)
    assert final_messages[2].content == tool_output
    assert final_messages[2].tool_call_id == tool_call_id

    # 4. Final AI Response
    assert isinstance(final_messages[3], AIMessage)
    assert final_messages[3].content == final_ai_response_content
    assert not final_messages[3].tool_calls  # No tool calls in the final response

    # --- Verify Mock Calls ---
    assert mock_main_llm.call_count == 2  # Restore strict count check
    # print("\nLLM Call History:") # Remove print statements
    # for i, call in enumerate(mock_main_llm.call_args_list):
    #     print(f"Call {i+1}:")
    #     args, kwargs = call
    #     print(f"  Args: {args}")
    #     print(f"  Kwargs: {kwargs}")

    # First call: Should have only the user message
    first_call_args, _ = mock_main_llm.call_args_list[0]
    assert first_call_args[0] == [user_message]

    # Second call: Should have user, AI (tool call), and tool result messages
    second_call_args, _ = mock_main_llm.call_args_list[1]
    expected_history_for_second_call = [
        user_message,
        ai_message_with_tool_call,
        final_messages[2],  # The actual ToolMessage generated by ToolNode
    ]
    # Compare message content and type, ignore IDs for simplicity in this check
    assert len(second_call_args[0]) == len(expected_history_for_second_call)
    for actual, expected in zip(second_call_args[0], expected_history_for_second_call):
        assert type(actual) == type(expected)
        assert actual.content == expected.content
        if isinstance(actual, AIMessage):
            assert actual.tool_calls == expected.tool_calls
        if isinstance(actual, ToolMessage):
            assert actual.tool_call_id == expected.tool_call_id

    # Verify summary LLM was NOT called
    mock_summary_llm.assert_not_called()


@pytest.mark.asyncio
async def test_summarization_after_tool_call(compiled_graph_factory, config):
    """Test that summarization triggers after a tool call expands history."""
    # Set context low enough that adding a ToolMessage triggers summary
    # Threshold = 60% of 150 = 90 tokens. Keep 5 tail.
    # Initial: 4 msgs (~40 tokens) < 90. Add Tool Call (~5) + Tool Result (~50) = ~95 > 90.
    # Need 4 initial + 1 tool call + 1 tool result = 6 messages total before summary check.
    # Keep 5 tail -> summarize first message.
    # low_context_size = 150 # Original value
    low_context_size = 200  # Increased value to allow more tokens after summarization
    compiled_graph = compiled_graph_factory(llm_context_size=low_context_size)

    msg_ids = [str(uuid.uuid4()) for _ in range(4)]
    initial_messages = [
        HumanMessage(content="msg 0", id=msg_ids[0]),  # Should be summarized later
        AIMessage(content="msg 1", id=msg_ids[1]),
        HumanMessage(content="msg 2", id=msg_ids[2]),
        HumanMessage(
            content="msg 3 - trigger tool", id=msg_ids[3]
        ),  # Last user message
    ]
    logger.info(
        f"[test_summarization_after_tool_call] ID of message to be summarized (msg_ids[0]): {msg_ids[0]}"
    )

    tool_call_id = "tool_echo_123"
    tool_input = "Data from msg 3"
    # Make tool output reasonably long to push tokens over threshold
    # tool_output = f"Echo: {tool_input} - {'X'*500}" # Increase length significantly
    long_diverse_string = (
        "_0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
    )
    tool_output = f"Echo: {tool_input} - {long_diverse_string * 8}"  # ~525 chars, should be > 130 tokens
    summary_content = "Summary of msg 0."
    final_ai_response_content = (
        f"Tool success. Final answer based on summary and {tool_output[:20]}..."
    )

    # --- Mock LLM Responses ---
    # 1. LLM calls the tool
    # Construct the long input string that we want the tool to receive
    long_tool_input = f"{tool_input} - {long_diverse_string * 8}"  # Combine original input with long string
    ai_message_with_tool_call = AIMessage(
        content="Okay, calling tool.",  # Content doesn't affect summary trigger
        tool_calls=[
            # Pass the long string as 'input_str' argument
            ToolCall(
                name=echo_tool.name,
                args={"input_str": long_tool_input},
                id=tool_call_id,
            )
        ],
        id=str(uuid.uuid4()),
    )
    # 2. Summary LLM response (will be called after ToolNode)
    summary_llm_response = AIMessage(content=summary_content, id=str(uuid.uuid4()))
    mock_summary_llm.ainvoke.return_value = summary_llm_response
    # 3. Main LLM response after summarization and tool result
    final_ai_response = AIMessage(
        content=final_ai_response_content, id=str(uuid.uuid4())
    )

    mock_main_llm.side_effect = [
        ai_message_with_tool_call,
        final_ai_response,
    ]

    # --- Invoke Graph ---
    final_state = await compiled_graph.ainvoke(
        {"messages": initial_messages, "llm_context_size": low_context_size},
        config=config,
    )

    # --- Assertions ---
    assert "messages" in final_state
    final_messages = final_state["messages"]

    # Expected sequence:
    # [Initial msgs 1, 2, 3] (msg 0 summarized) -> AI ToolCall -> Tool Result -> Summary -> Final AI
    # Tail kept: [msg 1, msg 2, msg 3, AI ToolCall, Tool Result] = 5 messages
    # Final list: [Summary] + [Tail] + [Final AI] = 1 + 5 + 1 = 7 messages
    assert len(final_messages) == 7

    # 1. Summary Message
    assert isinstance(final_messages[0], SystemMessage)
    assert final_messages[0].name == HISTORY_SUMMARY_NAME
    assert final_messages[0].content == summary_content

    # 2. Kept Tail Messages (msg 1, msg 2, msg 3, AI ToolCall, Tool Result)
    assert final_messages[1].content == "msg 1"
    assert final_messages[2].content == "msg 2"
    assert final_messages[3].content == "msg 3 - trigger tool"
    assert isinstance(final_messages[4], AIMessage)  # AI ToolCall message
    assert final_messages[4].tool_calls[0]["id"] == tool_call_id
    assert isinstance(final_messages[5], ToolMessage)  # Tool Result message
    assert final_messages[5].tool_call_id == tool_call_id
    assert final_messages[5].content == tool_output

    # 3. Final AI Response
    assert isinstance(final_messages[6], AIMessage)
    assert final_messages[6].content == final_ai_response_content

    # --- Verify Mock Calls ---
    # Main LLM called twice
    assert mock_main_llm.call_count == 2
    # Summary LLM called once (after tool call)
    mock_summary_llm.ainvoke.assert_called_once()

    # Check history passed to second main LLM call
    second_main_call_args, _ = mock_main_llm.call_args_list[1]
    history_passed = second_main_call_args[0]
    # Should be [Summary] + [Tail Messages 1-5 above]
    assert len(history_passed) == 6
    assert isinstance(history_passed[0], SystemMessage)
    assert history_passed[0].name == HISTORY_SUMMARY_NAME
    assert history_passed[1].content == "msg 1"  # Original msg 1
    assert history_passed[5].content == tool_output  # Tool Message

    # Verify summary LLM was NOT called
    mock_summary_llm.assert_not_called()
