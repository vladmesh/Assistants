# assistant_service/tests/assistants/test_langgraph_assistant.py

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from unittest.mock import AsyncMock, patch

import pytest

# Imports specific to the class under test
from assistants.langgraph.langgraph_assistant import LangGraphAssistant
from config import settings
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import Tool
from langgraph.checkpoint.memory import MemorySaver
from services.rest_service import RestServiceClient  # Import RestServiceClient
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
@patch(
    "assistants.langgraph.langgraph_assistant.ChatOpenAI",
    new_callable=lambda: MockChatOpenAI,
)
async def assistant_instance(
    mock_chat_openai, memory_saver, basic_config, time_tool_def, tool_factory, settings
):
    """Fixture to create an instance of LangGraphAssistant with mocks, using ToolFactory."""
    # Create mock rest_client explicitly
    mock_rest_client = AsyncMock(spec=RestServiceClient)
    fixture_user_id = "test_user_fixture"
    assistant_id = "test-asst-id"

    # Create ToolRead instance
    time_tool_def["created_at"] = datetime.fromisoformat(
        time_tool_def["created_at"].replace("Z", "+00:00")
    )
    time_tool_def["updated_at"] = datetime.fromisoformat(
        time_tool_def["updated_at"].replace("Z", "+00:00")
    )
    tool_schema_instance = ToolRead(**time_tool_def)

    # Create tools
    created_tools: List[Tool] = await tool_factory.create_langchain_tools(
        tool_definitions=[tool_schema_instance],
        user_id=fixture_user_id,
        assistant_id=assistant_id,
    )

    # Create LangGraphAssistant, explicitly passing mock_rest_client
    instance = LangGraphAssistant(
        assistant_id=assistant_id,
        name="test_assistant",
        config=basic_config,
        tools=created_tools,
        user_id=fixture_user_id,
        checkpointer=memory_saver,
        rest_client=mock_rest_client,  # Ensure this is passed
    )
    return instance


# @pytest.mark.asyncio
# async def test_initialization(assistant_instance):
#     """Test if the LangGraphAssistant initializes correctly."""
#     instance = await assistant_instance  # Await the coroutine fixture
#     assert isinstance(instance, LangGraphAssistant)
#     assert instance.llm is not None
#     assert instance.tools == [
#         "Get current time"
#     ]  # Assuming time_tool_def is the only tool
#     assert instance.graph is not None
#     assert instance.checkpointer is not None
#     assert instance.user_id == "test_user_fixture"
#     assert instance.assistant_id == "test-asst-id"
#     assert instance.rest_client is not None  # Check if rest_client is set
#     print(f"Initialized LangGraphAssistant: {instance}")


# @pytest.mark.asyncio
# async def test_process_message_stateless(assistant_instance, memory_saver):
#     """Test processing a single message using the graph."""
#     instance = await assistant_instance  # Await the fixture
#     user_id = "test_user_stateless"
#     thread_id = str(uuid.uuid4())
#     config = {"configurable": {"thread_id": thread_id}}
#
#     # Simulate sending a message
#     human_message = HumanMessage(content="What time is it?")
#     response_generator = instance.process_message(
#         human_message, user_id, thread_id, config
#     )
#
#     # Process the response
#     final_response = None
#     async for chunk in response_generator:
#         print(f"Received chunk: {chunk}")
#         if isinstance(chunk, dict) and "messages" in chunk:
#             # Check if it's the final state or intermediate messages
#             last_message = chunk["messages"][-1]
#             if isinstance(last_message, AIMessage):
#                 final_response = last_message.content
#                 print(f"Final AI message content: {final_response}")
#                 # Optional: Add specific assertion about the content if needed
#                 assert "current time" in final_response.lower()
#
#     assert final_response is not None, "No final AI message received"
#     # Check if the mock LLM was called
#     instance.llm.ainvoke.assert_called()


# @pytest.mark.asyncio
# async def test_process_message_stateful_memory(assistant_instance, memory_saver):
#     """Test if the assistant remembers context across messages using the checkpointer."""
#     instance: LangGraphAssistant = await assistant_instance  # Await the fixture
#     user_id = "test_user_stateful"
#     thread_id = str(uuid.uuid4())
#     config = {"configurable": {"thread_id": thread_id}}
#
#     # First message
#     first_message = HumanMessage(content="My favorite color is blue.")
#     response_gen1 = instance.process_message(
#         first_message, user_id, thread_id, config
#     )
#     async for _ in response_gen1:  # Consume the generator
#         pass
#     print("Processed first message.")
#
#     # Checkpoint should have been saved
#     checkpoint = await memory_saver.aget_tuple(config)
#     assert checkpoint is not None
#     print(f"Checkpoint after first message: {checkpoint.checkpoint}")
#     # You might want more specific assertions about the checkpoint content if possible
#
#     # Second message - ask about the favorite color
#     second_message = HumanMessage(content="What is my favorite color?")
#     response_gen2 = instance.process_message(
#         second_message, user_id, thread_id, config
#     )
#
#     final_response_content = ""
#     async for chunk in response_gen2:
#         if isinstance(chunk, dict) and "messages" in chunk:
#             last_message = chunk["messages"][-1]
#             if isinstance(last_message, AIMessage):
#                 final_response_content = last_message.content
#                 print(f"Received final response to second message: {final_response_content}")
#
#     # Check if the AI response includes the remembered color
#     assert (
#         "blue" in final_response_content.lower()
#     ), "Assistant did not remember the favorite color"
#     print("Assistant correctly remembered the favorite color.")
#
#     # Verify the mock LLM was called for both interactions (or adjust based on implementation)
#     # This check might be complex depending on how the mock is set up
#     assert instance.llm.ainvoke.call_count >= 2  # Ensure it was called at least twice
