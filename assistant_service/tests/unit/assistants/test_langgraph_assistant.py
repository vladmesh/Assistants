# assistant_service/tests/unit/assistants/test_langgraph_assistant.py

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import Tool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import (  # Keep using MemorySaver for unit tests
    MemorySaver,
)
from shared_models.api_schemas import ToolRead

# Adjust imports based on new structure
from assistants.langgraph.langgraph_assistant import LangGraphAssistant
from config.settings import Settings

# Assuming RestServiceClient mock is in unit/conftest.py
# from services.rest_service import RestServiceClient
from tools.factory import ToolFactory

# from tools.time_tool import TimeToolWrapper # Example tool


# Mock LLM remains the same
class MockChatLLM(BaseChatModel):
    # Keep the existing MockChatOpenAI implementation but rename for clarity
    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_message = messages[-1]
        content = f"Sync mock reply to: {getattr(last_message, 'content', '')}"
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_message = messages[-1]
        content = f"Async mock reply to: {getattr(last_message, 'content', '')}"
        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        await asyncio.sleep(0.01)
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "mock_chat_llm"

    def bind_tools(self, tools, **kwargs):
        # Simple mock implementation
        return self


# Use fixtures from conftest files


@pytest.fixture
def assistant_user_id() -> str:
    return "123"


@pytest.fixture
def assistant_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def time_tool_def() -> dict:
    """Provides a sample tool definition dictionary compatible with ToolRead."""
    now = datetime.now(UTC)
    # Ensure timestamps are properly formatted ISO strings
    created_at_iso = now.isoformat()
    updated_at_iso = now.isoformat()
    # Handle potential timezone offset format if needed by Pydantic/API
    if created_at_iso.endswith("+00:00"):
        created_at_iso = created_at_iso.replace("+00:00", "Z")
    if updated_at_iso.endswith("+00:00"):
        updated_at_iso = updated_at_iso.replace("+00:00", "Z")

    return {
        "id": str(uuid.uuid4()),
        "name": "current_time",
        "description": "Get current time",
        "tool_type": "time",
        "is_active": True,
        "assistant_id": None,
        "created_at": created_at_iso,
        "updated_at": updated_at_iso,
    }


@pytest.fixture
async def mock_tool_factory(mocker) -> ToolFactory:
    """Mock ToolFactory to control tool creation."""
    # Use the real factory but mock the method that creates tools
    factory = ToolFactory(settings=Settings())
    # Mock the creation method to return a predefined mock tool
    mock_tool_instance = Tool(
        name="mock_time", description="mock time tool", func=lambda: "mock time"
    )
    factory.create_langchain_tools = AsyncMock(return_value=[mock_tool_instance])
    return factory


@pytest.fixture
def assistant_config(time_tool_def) -> dict:
    """Provides a basic configuration dictionary for the assistant."""
    return {
        "model_name": "mock-model",
        "temperature": 0.5,
        "system_prompt": "You are a test assistant.",
        "timeout": 30,
        "tools": [time_tool_def],  # Pass the dict definition
    }


@pytest.fixture
def mock_checkpointer(mocker) -> BaseCheckpointSaver:
    """Mock BaseCheckpointSaver."""
    # Using MemorySaver as a stand-in mock for unit tests
    return MemorySaver()


@pytest.fixture
@patch(
    "assistants.langgraph.langgraph_assistant.ChatOpenAI",
    new_callable=lambda: MockChatLLM,
)
async def assistant_instance(
    mock_llm_class,  # The patched class mock
    mock_checkpointer: BaseCheckpointSaver,
    assistant_config: dict,
    mock_tool_factory: ToolFactory,  # Use mocked factory
    mock_rest_client: AsyncMock,  # Use mock from unit/conftest.py
    assistant_user_id: str,
    assistant_id: str,
) -> LangGraphAssistant:
    """Fixture to create an instance of LangGraphAssistant with mocks."""

    # Await the async fixture for the tool factory
    tool_factory_instance = await mock_tool_factory

    # Create tools using the mocked factory instance
    tool_definitions = [
        ToolRead(**tool_data) for tool_data in assistant_config.get("tools", [])
    ]
    created_tools = await tool_factory_instance.create_langchain_tools(
        tool_definitions=tool_definitions,
        user_id=assistant_user_id,
        assistant_id=assistant_id,
    )

    # Create LangGraphAssistant instance
    instance = LangGraphAssistant(
        assistant_id=assistant_id,
        name="test_assistant",
        config=assistant_config,
        tools=created_tools,  # Use tools from mocked factory
        user_id=assistant_user_id,
        rest_client=mock_rest_client,
        summarization_prompt="",
        context_window_size=1000,
    )
    # Ensure the LLM instance used is the mock
    assert isinstance(instance.llm, MockChatLLM)
    return instance


# --- Tests ---

pytestmark = pytest.mark.asyncio


async def test_initialization(assistant_instance: LangGraphAssistant):
    """Test if the LangGraphAssistant initializes correctly."""
    instance = await assistant_instance
    assert isinstance(instance, LangGraphAssistant)
    assert instance.llm is not None
    assert isinstance(instance.llm, MockChatLLM)
    assert instance.tools is not None
    assert len(instance.tools) > 0  # Check tools are present
    assert instance.compiled_graph is not None
    assert instance.user_id is not None
    assert instance.assistant_id is not None
    assert instance.rest_client is not None
    print(f"Initialized LangGraphAssistant: {instance.name}")


async def test_process_message_simple_response(assistant_instance: LangGraphAssistant):
    """Test processing a simple message expecting a direct LLM response."""
    instance = await assistant_instance
    user_id = instance.user_id

    # Arrange: Input message
    human_message = HumanMessage(content="Hello there!")

    # Act: Process the message
    final_response_content = await instance.process_message(
        human_message, user_id=user_id
    )

    assert final_response_content is not None, "No final AIMessage received"
    assert "Async mock reply to: Hello there!" in final_response_content


async def test_process_message_stateful_memory(
    assistant_instance: LangGraphAssistant,
):
    """Assistant remembers context across messages using the checkpointer."""
    instance = await assistant_instance
    user_id = instance.user_id

    # Arrange: First message
    first_message = HumanMessage(content="My favorite color is blue.")

    # Act: Process first message
    await instance.process_message(first_message, user_id=user_id)

    # Arrange: Second message
    second_message = HumanMessage(content="What is my favorite color?")

    # Act: Process second message
    response2 = await instance.process_message(second_message, user_id=user_id)

    assert response2 is not None
    assert "Async mock reply to: What is my favorite color?" in response2

    # Note: Checkpointing verification removed as we don't use checkpointers anymore


# TODO: Add tests for tool usage within the graph
# TODO: Add tests for error handling (e.g., tool execution error)
# TODO: Add tests for summarization node triggering
# TODO: Add tests for message truncation node triggering
