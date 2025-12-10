# assistant_service/src/assistants/langgraph/langgraph_assistant.py
import logging
from typing import Any
from uuid import UUID

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

from assistants.base_assistant import BaseAssistant
from assistants.langgraph.middleware import (
    AssistantAgentState,
    ContextLoaderMiddleware,
    DynamicPromptMiddleware,
    FinalizerMiddleware,
    MemoryRetrievalMiddleware,
    MessageSaverMiddleware,
    ResponseSaverMiddleware,
    SummarizationMiddleware,
)
from config.settings import settings
from services.rag_service import RagServiceClient
from services.rest_service import RestServiceClient
from utils.error_handler import AssistantError, MessageProcessingError

logger = logging.getLogger(__name__)


class LangGraphAssistant(BaseAssistant):
    """
    Assistant implementation using LangChain 1.x create_agent with middleware.
    Replaces the previous LangGraph custom graph approach.
    """

    agent: Any  # CompiledStateGraph from create_agent
    tools: list[Tool]
    rest_client: RestServiceClient
    rag_client: RagServiceClient
    llm: ChatOpenAI
    system_prompt_template: str = ""

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: dict,
        tools: list[Tool],
        user_id: str,
        rest_client: RestServiceClient,
        summarization_prompt: str,
        context_window_size: int,
        memory_retrieve_limit: int = 5,
        memory_retrieve_threshold: float = 0.6,
        **kwargs,
    ):
        """
        Initializes the LangGraphAssistant with create_agent and middleware.

        Args:
            assistant_id: Unique identifier for the assistant instance.
            name: Name of the assistant.
            config: Dictionary containing configuration parameters.
                    Expected keys: 'model_name', 'temperature', 'api_key' (optional),
                                   'system_prompt', 'timeout' (optional, default 60).
            tools: List of initialized Langchain Tool instances.
            user_id: The ID of the user associated with this assistant instance.
            rest_client: REST Service client instance.
            summarization_prompt: Prompt for summarizing conversation history.
            context_window_size: Maximum token limit for the context window.
            **kwargs: Additional keyword arguments.
        """
        raw_tool_definitions = config.get("tools", [])
        super().__init__(assistant_id, name, config, raw_tool_definitions, **kwargs)

        self.tools = tools
        self.user_id = user_id
        self.rest_client = rest_client
        self.timeout = self.config.get("timeout", 60)
        self.system_prompt_template = self.config["system_prompt"]
        self.assistant_id_uuid = UUID(assistant_id)

        self.summarization_prompt = summarization_prompt
        self.context_window_size = context_window_size

        self.memory_retrieve_limit = memory_retrieve_limit
        self.memory_retrieve_threshold = memory_retrieve_threshold
        self.rag_client = RagServiceClient(settings=settings)

        try:
            # Initialize LLM
            self.llm = self._initialize_llm()

            if not self.tools:
                logger.warning(
                    "LangGraphAssistant initialized with no tools.",
                    extra={"assistant_id": self.assistant_id, "user_id": self.user_id},
                )

            # Create the agent with middleware
            self.agent = self._create_agent()

            logger.info(
                "LangGraphAssistant initialized",
                extra={
                    "assistant_id": self.assistant_id,
                    "assistant_name": self.name,
                    "user_id": self.user_id,
                    "tools_count": len(self.tools),
                    "timeout": self.timeout,
                },
            )

        except Exception as e:
            logger.exception(
                "Failed to initialize LangGraphAssistant",
                extra={
                    "assistant_id": self.assistant_id,
                    "assistant_name": self.name,
                    "user_id": self.user_id,
                },
                exc_info=True,
            )
            raise AssistantError(
                f"Failed to initialize LangGraph assistant '{name}': {e}"
            ) from e

    async def _load_initial_data(self) -> None:
        """Placeholder hook for loading initial data (no-op)."""
        return None

    def _initialize_llm(self) -> ChatOpenAI:
        """Initializes the language model based on configuration."""
        model_name = self.config["model_name"]
        api_key = self.config.get("api_key", settings.OPENAI_API_KEY)

        if not api_key:
            raise ValueError(
                f"OpenAI API key is not configured for assistant {self.assistant_id}."
            )
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
        )

    def _create_agent(self) -> Any:
        """Creates the agent with middleware using LangChain 1.x create_agent."""
        try:
            # Create middleware instances
            middleware = [
                MessageSaverMiddleware(rest_client=self.rest_client),
                ContextLoaderMiddleware(rest_client=self.rest_client),
                MemoryRetrievalMiddleware(
                    rag_client=self.rag_client,
                    limit=self.memory_retrieve_limit,
                    threshold=self.memory_retrieve_threshold,
                ),
                SummarizationMiddleware(
                    summary_llm=self.llm,
                    rest_client=self.rest_client,
                    summarization_prompt=self.summarization_prompt,
                    system_prompt_template=self.system_prompt_template,
                ),
                DynamicPromptMiddleware(
                    system_prompt_template=self.system_prompt_template
                ),
                ResponseSaverMiddleware(rest_client=self.rest_client),
                FinalizerMiddleware(rest_client=self.rest_client),
            ]

            return create_agent(
                model=self.llm,
                tools=self.tools,
                system_prompt=self.system_prompt_template,
                middleware=middleware,
                state_schema=AssistantAgentState,
            )
        except Exception as e:
            raise AssistantError(f"Failed to create agent: {str(e)}", self.name) from e

    async def process_message(
        self,
        message: BaseMessage,
        user_id: str,
        log_extra: dict[str, Any] | None = None,
    ) -> str | None:
        """Processes a single message using the agent.

        Args:
            message: The incoming message from the user or system.
            user_id: User ID as string.
            log_extra: Additional logging context.

        Returns:
            Optional[str]: Response string or None if no response needed.
        """
        if self.user_id != user_id:
            logger.error(
                f"Mismatch user_id: assistant instance for "
                f"{self.user_id} received message for {user_id}"
            )
            raise ValueError("User ID mismatch")

        combined_log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": self.user_id,
        }
        if log_extra:
            combined_log_extra.update(log_extra)

        try:
            # Prepare initial state with custom fields
            initial_input = {
                "messages": [message],
                "user_id": user_id,
                "assistant_id": self.assistant_id,
                "llm_context_size": self.context_window_size,
                "triggered_event": None,
                "log_extra": combined_log_extra,
                "initial_message_id": None,
                "current_summary_content": None,
                "newly_summarized_message_ids": None,
                "relevant_memories": None,
            }

            # Invoke the agent
            try:
                result = await self.agent.ainvoke(initial_input)

                if not result or "messages" not in result:
                    raise MessageProcessingError(
                        "Agent execution finished but result is missing or invalid.",
                        self.name,
                    )

                # Extract the response from the result
                ai_response = None
                final_messages = result["messages"]

                if final_messages:
                    last_message = final_messages[-1]
                    if isinstance(last_message, AIMessage):
                        ai_response = last_message.content
                        response_preview = ai_response[:100] if ai_response else ""
                        logger.info(
                            f"Successfully processed message. "
                            f"Response: {response_preview}...",
                            extra=combined_log_extra,
                        )
                    elif isinstance(last_message, ToolMessage):
                        logger.info(
                            "Processing finished with a ToolMessage. "
                            "No response sent to user.",
                            extra=combined_log_extra,
                        )

                return ai_response

            except Exception as e:
                # Log the error and re-raise
                logger.exception(
                    f"Error during agent execution: {e}",
                    exc_info=True,
                    extra=combined_log_extra,
                )
                raise MessageProcessingError(
                    f"Unexpected error processing message: {e}", self.name
                ) from e

        except Exception as e:
            logger.exception(
                f"Failed to process message for user {user_id}",
                exc_info=True,
                extra=combined_log_extra,
            )
            raise MessageProcessingError(
                f"Failed to process message: {e}", self.name
            ) from e

    async def close(self):
        """Cleans up resources."""
        if self.rest_client:
            await self.rest_client.close_session()
            logger.info(
                "REST client session closed.", extra={"assistant_id": self.assistant_id}
            )
        if self.rag_client:
            await self.rag_client.close()
            logger.info(
                "RAG client session closed.", extra={"assistant_id": self.assistant_id}
            )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
