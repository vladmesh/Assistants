import asyncio
import os
from typing import Any, List, Optional

import pytest
import pytest_asyncio
import redis.asyncio as redis
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from openai import OpenAI

from shared_models.api_schemas.assistant import AssistantRead

# Fixtures for integration tests requiring real external services
# These might be marked with 'external_api'


@pytest.fixture(scope="session")
@pytest.mark.external_api
def real_llm():
    """Real LangChain ChatOpenAI model (requires API key and network)."""
    # Consider adding error handling if key is missing
    return ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.7)


@pytest.fixture(scope="session")
@pytest.mark.external_api
def real_openai_client():
    """Real OpenAI client (requires API key and network)."""
    return OpenAI()


@pytest.fixture(scope="session")
def redis_url():
    """Provides the Redis URL for the test container."""
    # Assumes the test environment (e.g., docker-compose.test.yml) sets this.
    # Defaulting to localhost if not set, adjust if needed.
    return os.getenv("TEST_REDIS_URL")


@pytest_asyncio.fixture
async def test_redis(redis_url):
    """Provides a real Redis connection instance for integration tests."""
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        await client.ping()  # Check connection
        await client.flushdb()  # Clean before test
        yield client
        await client.flushdb()  # Clean after test
    finally:
        await client.aclose()


class MockChatLLMIntegration(BaseChatModel):
    """
    Mock Chat LLM specifically for integration tests.
    Returns a predictable response based on the last message content.
    """

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a mock async response."""
        last_message = messages[-1] if messages else None
        input_content = "No input message found"

        # Extract content safely from various message types
        if hasattr(last_message, "content"):
            input_content = str(last_message.content)

        # Construct a predictable response for assertion
        content = f"Integration mock reply to: {input_content}"
        message = AIMessage(
            content=content, id="ai-mock-integration-msg"
        )  # Add id for potential extra checks
        generation = ChatGeneration(message=message)
        await asyncio.sleep(0.01)  # Simulate a tiny network delay

        # The result structure expected by LangChain/LangGraph
        return ChatResult(generations=[generation])


class MockRestServiceIntegration:
    """Mock REST service for integration tests."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url
        self.user_id = 123

    async def get_user_secretary_assignment(
        self, user_id: int
    ) -> Optional[AssistantRead]:
        """Mock get_user_secretary functionality."""
        return AssistantRead(id=123, name="Mock Secretary")

    @property
    def _llm_type(self) -> str:
        """Return type of LLM."""
        return "mock_chat_llm_integration"

    def bind_tools(self, tools, **kwargs):
        """Mock bind_tools functionality for compatibility."""
        # In many integration tests focusing on flow, complex tool binding isn't needed.
        # This basic implementation allows the code calling bind_tools to proceed.
        print(
            f"MockChatLLMIntegration: bind_tools called with {len(tools)} tools (kwargs: {kwargs}). Returning self."
        )
        return self  # Return self allows potential chaining like .bind(stop=...)

    def close(self):
        """Mock close functionality."""
        print("MockRestServiceIntegration: close called")
        return None
