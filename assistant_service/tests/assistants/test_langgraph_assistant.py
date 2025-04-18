# assistant_service/tests/assistants/test_langgraph_assistant.py

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from unittest.mock import AsyncMock, patch

import pytest

# Imports specific to the class under test
from assistants.langgraph_assistant import LangGraphAssistant
from config import settings
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import Tool
from langgraph.checkpoint.memory import MemorySaver
from tools.factory import ToolFactory  # Import ToolFactory
from tools.time_tool import TimeToolWrapper  # Import a real simple tool

from shared_models.api_schemas import ToolRead  # Import ToolRead instead


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


@pytest.fixture(scope="module")
def settings():
    """Mock the global settings for tests."""
    with patch("config.settings.settings") as mock_settings:
        # Set required attributes on the mock
        mock_settings.openai_api_key = "mock-openai-key"
        mock_settings.tavily_api_key = "mock-tavily-key"
        mock_settings.redis_url = "redis://localhost:6379/0"
        mock_settings.log_level = "DEBUG"
        mock_settings.rest_service_url = "http://mock-rest-service"
        mock_settings.google_calendar_service_url = "http://mock-calendar-service"
        mock_settings.google_token_storage_path = "/tmp/mock_token.json"
        mock_settings.google_credentials_path = "/tmp/mock_credentials.json"
        yield mock_settings


@pytest.fixture(scope="module")
def tool_factory(settings):
    return ToolFactory(settings=settings)


@pytest.fixture
def basic_config():
    """Provides a basic configuration dictionary for the assistant."""
    return {
        "model_name": "mock-model",
        "temperature": 0.5,
        "api_key": "mock-key",  # Can be overridden by global settings if needed
        "system_prompt": "You are a test assistant.",
        "timeout": 30,
        # Include raw tool definitions if BaseAssistant init requires it
        "tools": [
            {
                "name": "current_time",
                "description": "Get current time",
                "tool_type": "time",
            }
        ],
    }


@pytest.fixture
def time_tool_def():
    """Provides a sample tool definition dictionary compatible with ToolRead."""
    # Adjusted to match ToolRead schema fields
    return {
        "id": uuid.uuid4(),
        "name": "current_time",
        "description": "Get current time",
        "tool_type": "time",  # Assuming ToolType enum includes 'time'
        "is_active": True,
        "input_schema": None,  # ToolRead expects dict or None
        "assistant_id": None,
        "created_at": datetime.now(timezone.utc),  # ToolRead includes timestamps
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
@patch("assistants.langgraph_assistant.ChatOpenAI", new_callable=lambda: MockChatOpenAI)
async def assistant_instance(
    mock_chat_openai, memory_saver, basic_config, time_tool_def, tool_factory, settings
):
    """Fixture to create an instance of LangGraphAssistant with mocks, using ToolFactory."""
    # Mock Rest Client if ToolFactory needs it (depends on tool types)
    # For simple tools like 'time', it might not be necessary.
    # If tools requiring REST calls are used, mock tool_factory.rest_client
    # tool_factory.rest_client = AsyncMock() # Example if needed

    # Define a fixture user_id
    fixture_user_id = "test_user_fixture"

    # Create ToolRead instance from the dictionary definition
    tool_schema_instance = ToolRead(**time_tool_def)

    # Create tools using the factory
    created_tools: List[Tool] = await tool_factory.create_langchain_tools(
        tool_definitions=[tool_schema_instance],  # Pass the ToolRead instance
        user_id=fixture_user_id,
        assistant_id="test-asst-id",
    )

    # Create the LangGraphAssistant instance
    instance = LangGraphAssistant(
        assistant_id="test-asst-id",
        name="test_assistant",
        config=basic_config,
        tools=created_tools,  # Pass the created tools list
        user_id=fixture_user_id,  # Pass the user ID
        checkpointer=memory_saver,
        # tool_definitions argument is removed from LangGraphAssistant init
        # tool_factory argument is removed
    )
    # Add system prompt message as an attribute for easier testing
    instance.system_prompt_message = SystemMessage(content=instance.system_prompt)
    return instance


@pytest.mark.asyncio
async def test_initialization(assistant_instance):
    """Test if the LangGraphAssistant initializes correctly."""
    instance = await assistant_instance  # Await the coroutine fixture
    assert instance is not None
    assert instance.name == "test_assistant"
    assert instance.assistant_id == "test-asst-id"
    assert instance.user_id == "test_user_fixture"  # Check user_id storage
    assert isinstance(instance.llm, MockChatOpenAI)
    assert instance.checkpointer is not None
    assert len(instance.tools) == 1  # Check if tools list is populated
    assert isinstance(instance.tools[0], TimeToolWrapper)  # Check for correct tool type
    assert (
        instance.tools[0].name == "current_time"
    )  # Check name from ToolModel used by factory
    assert instance.compiled_graph is not None  # Check if graph is compiled
    # Check default system prompt if not overridden
    assert instance.system_prompt == "You are a test assistant."
    # Get timeout from the instance config after awaiting
    assert instance.timeout == instance.config.get("timeout", 60)


@pytest.mark.asyncio
async def test_process_message_stateless(assistant_instance, memory_saver):
    """Test processing a single message using the graph."""
    instance = await assistant_instance  # Await the fixture
    user_id = "user123"
    input_message = HumanMessage(content="What time is it?")

    # Mock the agent runnable's response
    # create_react_agent returns a dict with 'messages' key
    mock_response_message = AIMessage(content="It's mock time!")
    instance.agent_runnable.ainvoke = AsyncMock(
        return_value={"messages": [mock_response_message]}
    )
    # Mock the compiled_graph to return a mock state
    expected_state = {
        "messages": [input_message, mock_response_message],
        "dialog_state": ["idle"],
        "last_activity": datetime.now(timezone.utc),
        "user_id": user_id,
    }
    instance.compiled_graph.ainvoke = AsyncMock(return_value=expected_state)

    response = await instance.process_message(input_message, user_id)

    assert response == "It's mock time!"
    # Verify compiled_graph was called with correct parameters
    instance.compiled_graph.ainvoke.assert_called_once()
    # No need to check checkpointer state directly as we mocked the graph


@pytest.mark.asyncio
async def test_process_message_stateful_memory(assistant_instance, memory_saver):
    """Test if the assistant remembers context across messages using the checkpointer."""
    instance = await assistant_instance  # Await the fixture
    user_id = "user456"
    # thread_id = f"user_{user_id}" # Variable not used
    # config = {"configurable": {"thread_id": thread_id}} # Variable not used

    # Первое сообщение
    input1 = HumanMessage(content="My name is Bob.")
    mock_response1 = AIMessage(content="Hi Bob!")

    # Создаем новый мок для первого вызова
    first_mock = AsyncMock()
    first_state = {
        "messages": [input1, mock_response1],
        "dialog_state": ["idle"],
        "last_activity": datetime.now(timezone.utc),
        "user_id": user_id,
    }
    first_mock.return_value = first_state
    instance.compiled_graph.ainvoke = first_mock

    response1 = await instance.process_message(input1, user_id)
    assert response1 == "Hi Bob!"
    first_mock.assert_called_once()

    # Создаем отдельный мок для второго вызова
    input2 = HumanMessage(content="What is my name?")
    mock_response2 = AIMessage(content="Your name is Bob.")

    second_mock = AsyncMock()
    second_state = {
        "messages": [input1, mock_response1, input2, mock_response2],
        "dialog_state": ["idle"],
        "last_activity": datetime.now(timezone.utc),
        "user_id": user_id,
    }
    second_mock.return_value = second_state
    instance.compiled_graph.ainvoke = second_mock

    response2 = await instance.process_message(input2, user_id)
    assert response2 == "Your name is Bob."
    second_mock.assert_called_once()

    # Проверяем аргументы вызовов через отдельные моки
    first_call_args = first_mock.call_args[0][0]
    second_call_args = second_mock.call_args[0][0]

    # Ожидаем, что SystemMessage будет первым в списке
    expected_first_messages = [
        instance.system_prompt_message,
        input1,
    ]  # SystemMessage + HumanMessage
    expected_second_messages = [
        instance.system_prompt_message,
        input2,
    ]  # SystemMessage + HumanMessage

    assert "messages" in first_call_args
    # Сравниваем содержимое, а не объекты напрямую, если system_prompt_message создается динамически
    assert len(first_call_args["messages"]) == len(expected_first_messages)
    assert first_call_args["messages"][0].content == expected_first_messages[0].content
    assert first_call_args["messages"][1] == expected_first_messages[1]
    assert first_call_args["user_id"] == user_id
    # Check other state elements passed
    assert first_call_args["triggered_event"] is None
    # The initial state passed to invoke should be 'processing'
    assert first_call_args["dialog_state"] == ["processing"]

    assert "messages" in second_call_args
    assert len(second_call_args["messages"]) == len(expected_second_messages)
    assert (
        second_call_args["messages"][0].content == expected_second_messages[0].content
    )
    assert second_call_args["messages"][1] == expected_second_messages[1]
    assert second_call_args["user_id"] == user_id
    # Check other state elements passed
    assert second_call_args["triggered_event"] is None
    # The initial state passed to invoke should be 'processing'
    assert second_call_args["dialog_state"] == ["processing"]
