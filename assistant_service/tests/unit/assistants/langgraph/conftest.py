# tests/unit/assistants/langgraph/conftest.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# Import necessary components with corrected paths
from assistants.langgraph.graph_builder import build_full_graph
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledGraph

# Import the tool with corrected path
from tools.user_fact_tool import UserFactTool

# Assume mock_rest_client and mock_settings are available from tests/unit/conftest.py
# If they need specific configurations here, define them locally.


@pytest.fixture
def mock_langgraph_llm() -> MagicMock:
    """Mock LLM specifically for LangGraph tests."""
    llm = MagicMock(spec=BaseChatModel)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked LLM response"))
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


@pytest.fixture
def mock_summary_llm() -> MagicMock:
    """Mock LLM for summarization node tests."""
    llm = MagicMock(spec=BaseChatModel)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked summary"))
    return llm


@pytest.fixture
def memory_saver() -> MemorySaver:
    """In-memory checkpointer for graph tests."""
    return MemorySaver()


@pytest.fixture
def user_fact_tool_instance(
    mock_rest_client: MagicMock, mock_settings: MagicMock
) -> UserFactTool:
    """Real UserFactTool instance with mocked dependencies."""
    # Assuming mock_rest_client and mock_settings fixtures are available
    # from higher-level conftest files (e.g., tests/unit/conftest.py)
    tool = UserFactTool(
        name="save_user_fact",
        description="Saves a specific fact about the user.",
        rest_client=mock_rest_client,
        settings=mock_settings,
        # Provide missing user_id and assistant_id required by UserFactTool
        user_id="test-user-for-tool",
        assistant_id="test-asst-for-tool",
        tool_id="test-toolid-for-tool",
    )
    # No need to mock _arun, it uses the mocked rest_client
    return tool


@pytest.fixture
def compiled_test_graph(
    mock_langgraph_llm: MagicMock,
    mock_summary_llm: MagicMock,
    mock_rest_client: MagicMock,
    memory_saver: MemorySaver,
    user_fact_tool_instance: UserFactTool,  # Use the specific instance fixture
    summarization_prompt: str,
    context_window_size: int,
) -> CompiledGraph:
    """Compiled LangGraph with mocks for unit testing graph logic."""
    tools_list = [user_fact_tool_instance]

    # We need a mock for the function passed to the 'assistant' node.
    # This function is usually `create_react_agent` or similar.
    # Let's mock its behavior: return an AIMessage or a Tool call.
    mock_run_node_fn = AsyncMock()
    # Example: Default behavior is a simple response
    mock_run_node_fn.return_value = {
        "messages": [AIMessage(content="Default mock response")]
    }

    graph = build_full_graph(
        run_node_fn=mock_run_node_fn,  # Pass the mock function
        tools=tools_list,
        checkpointer=memory_saver,
        rest_client=mock_rest_client,
        system_prompt_text="Test system prompt",
        summary_llm=mock_summary_llm,
        summarization_prompt=summarization_prompt,
        context_window_size=context_window_size,
    )
    return graph


@pytest.fixture
def graph_test_thread_id() -> str:
    """Provides a unique thread ID for graph tests."""
    return f"test-thread-{uuid.uuid4()}"
