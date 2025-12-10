# assistant_service/src/assistants/langgraph/langgraph_assistant.py
import logging
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent

from assistants.base_assistant import BaseAssistant
from assistants.langgraph.graph_builder import build_full_graph
from assistants.langgraph.prompt_context_cache import PromptContextCache
from assistants.langgraph.state import AssistantState
from assistants.langgraph.utils.logging_utils import log_messages_to_file
from assistants.langgraph.utils.token_counter import count_tokens
from config.settings import settings
from services.rag_service import RagServiceClient
from services.rest_service import RestServiceClient
from utils.error_handler import AssistantError, MessageProcessingError

logger = logging.getLogger(__name__)


class LangGraphAssistant(BaseAssistant):
    """
    Assistant implementation using LangGraph with a custom graph structure
    similar to the old BaseLLMChat, supporting database-based message storage.
    Handles fact caching internally.
    """

    compiled_graph: CompiledStateGraph
    agent_runnable: Any
    tools: list[Tool]
    rest_client: RestServiceClient
    rag_client: RagServiceClient
    llm: ChatOpenAI

    # --- NEW: Shared Cache Object and Template --- #
    prompt_context_cache: PromptContextCache
    system_prompt_template: str = ""  # Will be filled in __init__
    # ---------------------------------------------

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: dict,
        tools: list[Tool],  # Receive initialized tools
        user_id: str,  # Receive user_id
        rest_client: RestServiceClient,  # Add rest_client parameter
        summarization_prompt: str,
        context_window_size: int,
        # Memory V2 settings
        memory_retrieve_limit: int = 5,
        memory_retrieve_threshold: float = 0.6,
        **kwargs,
    ):
        """
        Initializes the LangGraphAssistant with pre-initialized tools.

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
        raw_tool_definitions = config.get(
            "tools", []
        )  # Get raw defs if they exist in config, else empty
        super().__init__(assistant_id, name, config, raw_tool_definitions, **kwargs)

        # Store pre-initialized tools and user_id
        self.tools = tools
        self.user_id = user_id  # Store user_id if needed by other methods
        self.rest_client = rest_client  # Store the rest_client
        self.timeout = self.config.get("timeout", 60)  # Default timeout 60 seconds
        self.system_prompt_template = self.config[
            "system_prompt"
        ]  # NEW: Store as template
        self.assistant_id_uuid = UUID(assistant_id)

        # --- Initialize Shared Cache --- #
        self.prompt_context_cache = PromptContextCache()
        # Initial flags are True by default in the cache object
        # ------------------------------- #

        # --- Initialize New Parameters --- #
        self.summarization_prompt = summarization_prompt
        self.context_window_size = context_window_size
        # --------------------------------- #

        # --- Memory V2 Parameters --- #
        self.memory_retrieve_limit = memory_retrieve_limit
        self.memory_retrieve_threshold = memory_retrieve_threshold
        self.rag_client = RagServiceClient(settings=settings)
        # ----------------------------- #

        try:
            # 1. Initialize LLM
            self.llm = self._initialize_llm()

            if not self.tools:
                logger.warning(
                    "LangGraphAssistant initialized with no tools.",
                    extra={"assistant_id": self.assistant_id, "user_id": self.user_id},
                )

            # 3. Create the core agent runnable (using self.tools)
            # This runnable function will be used as the 'assistant' node
            self.agent_runnable = self._create_agent_runnable()

            # 4. Build and compile the full graph
            self.compiled_graph = build_full_graph(
                tools=self.tools,
                # Summary LLM needed for summary node logic
                summary_llm=self.llm,
                # REST client needed for summary node SAVE logic
                rest_client=self.rest_client,
                # RAG client for Memory V2 retrieval
                rag_client=self.rag_client,
                prompt_context_cache=self.prompt_context_cache,
                system_prompt_template=self.system_prompt_template,
                agent_runnable=self.agent_runnable,
                timeout=self.timeout,
                summarization_prompt=self.summarization_prompt,
                context_window_size=self.context_window_size,
                # Memory V2 settings
                memory_retrieve_limit=self.memory_retrieve_limit,
                memory_retrieve_threshold=self.memory_retrieve_threshold,
            )

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
        model_name = self.config["model_name"]  # Требуем обязательное значение
        api_key = self.config.get("api_key", settings.OPENAI_API_KEY)

        if not api_key:
            raise ValueError(
                f"OpenAI API key is not configured for assistant {self.assistant_id}."
            )
        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
        )

    def _create_agent_runnable(self) -> Any:
        """Creates the core agent runnable (e.g., using create_react_agent).

        Ensures the system prompt modifier is used.
        """
        try:
            # Pass the ORIGINAL LLM and use the 'prompt' parameter for our modifier
            return create_react_agent(
                self.llm,  # Pass original LLM
                self.tools,
                prompt=self._add_system_prompt_modifier,  # Pass our modifier function
            )
        except Exception as e:
            raise AssistantError(
                f"Failed to create agent runnable: {str(e)}", self.name
            ) from e

    # --- Prompt Modifier ---
    async def _add_system_prompt_modifier(
        self,
        state: AssistantState,
    ) -> list[BaseMessage]:
        """
        Dynamically creates the SystemMessage using state data.
        Memory V2: Uses relevant_memories from state instead of cached facts.
        """
        log_extra = {"assistant_id": self.assistant_id, "user_id": self.user_id}
        current_messages = state.get("messages", [])

        # Get memories from state (populated by retrieve_memories node in future)
        relevant_memories = state.get("relevant_memories", [])
        current_summary = state.get("current_summary_content")

        # Format memories for prompt
        memories_str = (
            "\n".join(f"- {m.get('text', '')}" for m in relevant_memories)
            if relevant_memories
            else "Нет сохраненной информации о пользователе."
        )
        summary_str = (
            current_summary if current_summary else "Нет предыдущей истории диалога."
        )

        try:
            formatted_prompt = self.system_prompt_template.format(
                summary_previous=summary_str, memories=memories_str
            )
        except KeyError as e:
            logger.error(
                f"Missing key in system_prompt_template: {e}. Using template as is.",
                extra=log_extra,
            )
            formatted_prompt = self.system_prompt_template

        system_message = SystemMessage(content=formatted_prompt)
        final_messages: list[BaseMessage] = [system_message] + list(current_messages)

        try:
            total_tokens = count_tokens(final_messages)
            await log_messages_to_file(
                assistant_id=self.assistant_id,
                user_id=self.user_id,
                messages=final_messages,
                total_tokens=total_tokens,
                context_limit=self.context_window_size,
                log_file_path=f"src/logs/message_logs/message_log_{self.user_id}.log",
                step_name="_add_system_prompt_modifier",
            )
        except Exception as log_e:
            logger.warning(f"Failed to log messages to file: {log_e}", extra=log_extra)

        return final_messages

    async def process_message(
        self,
        message: BaseMessage,
        user_id: str,
        log_extra: dict[str, Any] | None = None,
    ) -> str | None:
        """Processes a single message using the compiled LangGraph graph.

        Args:
            message: The incoming message from the user or system.
            user_id: User ID as string.
            log_extra: Additional logging context.

        Returns:
            Optional[str]: Response string or None if no response needed.
        """
        if self.user_id != user_id:
            logger.error(
                "Mismatch user_id: assistant instance for "
                f"{self.user_id} received message for {user_id}"
            )
            raise ValueError("User ID mismatch")

        # Common logging context
        combined_log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": self.user_id,
        }
        if log_extra:
            combined_log_extra.update(log_extra)

        try:
            # Формируем AssistantState для графа
            initial_state = AssistantState(
                messages=[],
                initial_message=message,
                user_id=user_id,
                assistant_id=self.assistant_id,
                llm_context_size=self.context_window_size,
                triggered_event=None,
                log_extra=combined_log_extra,
                initial_message_id=None,
                current_summary_content=None,
                newly_summarized_message_ids=None,
                relevant_memories=None,  # Will be populated by retrieve_memories node
            )

            # Запускаем граф
            try:
                final_state = await self.compiled_graph.ainvoke(
                    input=dict(initial_state),
                    config=None,  # Чекпоинтер больше не используется
                )

                if not final_state or "messages" not in final_state:
                    raise MessageProcessingError(
                        "Graph execution finished but final state "
                        "is missing or invalid.",
                        self.name,
                    )

                # Извлекаем ответ из финального состояния
                ai_response = None
                final_messages = final_state["messages"]

                # Extract the last message as the response
                if final_messages:
                    last_message = final_messages[-1]
                    if isinstance(last_message, AIMessage):
                        ai_response = last_message.content
                        logger.info(
                            "Successfully processed message. "
                            f"Response: {ai_response[:100]}...",
                            extra=combined_log_extra,
                        )
                    elif isinstance(last_message, ToolMessage):
                        logger.info(
                            "Processing finished with a ToolMessage "
                            "(likely from fact save/reminder trigger "
                            "processing). No response sent to user.",
                            extra=combined_log_extra,
                        )

                return ai_response

            except Exception as e:
                # В случае ошибки во время выполнения графа, обновляем статус сообщения
                message_id = initial_state.get("initial_message_id")
                if message_id:
                    try:
                        await self.rest_client.update_message(
                            message_id=message_id, message_update={"status": "error"}
                        )
                    except Exception as update_error:
                        logger.error(
                            "Failed to update message status after error: "
                            f"{update_error}",
                            exc_info=True,
                            extra=combined_log_extra,
                        )

                # Логируем ошибку выполнения графа и прокидываем ее выше
                logger.exception(
                    f"Error during graph execution: {e}",
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
        """Cleans up resources, like closing the REST and RAG client sessions."""
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

    # Add __aenter__ and __aexit__ for async context management
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# TODO:
# 1. Add proper error handling within the nodes (e.g., for API errors from LLM/Tools).
# 2. Implement timeout mechanism within the nodes or graph execution.
# 3. Consider adding state transitions for 'error' and 'timeout' in dialog_state.
# 4. Refine how system prompts are handled (ensure they are always first message).
# 5. Test checkpointing and state recovery thoroughly.
# 6. Add logging for state transitions.
