# assistant_service/src/assistants/langgraph/langgraph_assistant.py
import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

# Project specific imports
from assistants.base_assistant import BaseAssistant  # Absolute import from src
from assistants.langgraph.graph_builder import build_full_graph
from assistants.langgraph.prompt_context_cache import PromptContextCache
from assistants.langgraph.state import AssistantState
from assistants.langgraph.utils.logging_utils import log_messages_to_file
from assistants.langgraph.utils.token_counter import count_tokens
from config.settings import settings  # To get API keys if not in assistant config

# Base classes and core types
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

# LangGraph components
from langgraph.graph.state import CompiledGraph
from langgraph.prebuilt import create_react_agent  # Import create_react_agent
from services.rest_service import RestServiceClient  # Import RestServiceClient
from utils.error_handler import AssistantError, MessageProcessingError

from shared_models.api_schemas.message import MessageCreate, MessageRead

# Import the specific schema needed
from shared_models.api_schemas.user_fact import UserFactRead

from .constants import FACT_SAVE_SUCCESS_MESSAGE, FACT_SAVE_TOOL_NAME

logger = logging.getLogger(__name__)


class LangGraphAssistant(BaseAssistant):
    """
    Assistant implementation using LangGraph with a custom graph structure
    similar to the old BaseLLMChat, supporting database-based message storage.
    Handles fact caching internally.
    """

    compiled_graph: CompiledGraph
    agent_runnable: Any
    tools: List[Tool]
    rest_client: RestServiceClient
    llm: ChatOpenAI

    # --- NEW: Shared Cache Object and Template --- #
    prompt_context_cache: PromptContextCache
    system_prompt_template: str = ""  # Will be filled in __init__
    # ---------------------------------------------

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: Dict,
        tools: List[Tool],  # Receive initialized tools
        user_id: str,  # Receive user_id
        rest_client: RestServiceClient,  # Add rest_client parameter
        summarization_prompt: str,
        context_window_size: int,
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
        self.max_tokens = self.config.get("max_tokens", 7500)
        self.assistant_id_uuid = UUID(assistant_id)

        # --- Initialize Shared Cache --- #
        self.prompt_context_cache = PromptContextCache()
        # Initial flags are True by default in the cache object
        # ------------------------------- #

        # --- Initialize New Parameters --- #
        self.summarization_prompt = summarization_prompt
        self.context_window_size = context_window_size
        # --------------------------------- #

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
                summary_llm=self.llm,  # Summary LLM still needed for summary node logic
                rest_client=self.rest_client,  # REST client needed for summary node SAVE logic
                prompt_context_cache=self.prompt_context_cache,  # Pass cache object
                system_prompt_template=self.system_prompt_template,  # Pass template
                agent_runnable=self.agent_runnable,
                timeout=self.timeout,
                summarization_prompt=self.summarization_prompt,
                context_window_size=self.context_window_size,
            )

            logger.info(
                "LangGraphAssistant initialized (with PromptContextCache)",
                extra={
                    "assistant_id": self.assistant_id,
                    "assistant_name": self.name,
                    "user_id": self.user_id,
                    "tools_count": len(self.tools),
                    "timeout": self.timeout,
                    "initial_needs_fact_refresh": self.prompt_context_cache.needs_fact_refresh,
                    "initial_needs_summary_refresh": self.prompt_context_cache.needs_summary_refresh,
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

    def _initialize_llm(self) -> ChatOpenAI:
        """Initializes the language model based on configuration."""
        model_name = self.config.get("model_name", "gpt-4o-mini")  # Default model
        self.config.get("temperature", 0.7)
        api_key = self.config.get("api_key", settings.OPENAI_API_KEY)

        if not api_key:
            raise ValueError(
                f"OpenAI API key is not configured for assistant {self.assistant_id}."
            )
        return ChatOpenAI(
            model=model_name,
            # temperature=temperature,
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

    # --- NEW: Method to load initial data ---
    async def _load_initial_data(self):
        """Fetches initial summary and facts and updates the shared cache."""
        try:
            user_id_int = int(self.user_id)
        except ValueError:
            logger.error(
                f"Invalid user_id format: {self.user_id}. Cannot load initial data."
            )
            # Reset cache state on error
            self.prompt_context_cache = PromptContextCache()
            return

        log_extra = {"assistant_id": self.assistant_id, "user_id": self.user_id}
        logger.info("Loading initial summary and facts into cache...", extra=log_extra)

        results = await asyncio.gather(
            self.rest_client.get_user_summary(
                user_id=user_id_int, secretary_id=self.assistant_id_uuid
            ),
            self.rest_client.get_user_facts(user_id=user_id_int),
            return_exceptions=True,
        )

        # Process Summary Result
        summary_result = results[0]
        loaded_summary = None
        if isinstance(summary_result, Exception):
            logger.error(
                f"Failed to load initial summary: {summary_result}",
                exc_info=isinstance(summary_result, Exception),
                extra=log_extra,
            )
            self.prompt_context_cache.require_summary_refresh()  # Ensure retry
        elif summary_result and hasattr(summary_result, "summary_text"):
            loaded_summary = summary_result.summary_text
            logger.info("Successfully loaded initial summary.", extra=log_extra)
        else:
            logger.info(
                "No initial summary found or unexpected format.", extra=log_extra
            )
        # Update cache (even if None, resets flag)
        self.prompt_context_cache.update_summary(loaded_summary)

        # Process Facts Result
        facts_result = results[1]
        loaded_fact_texts: Optional[List[str]] = None
        if isinstance(facts_result, Exception):
            logger.error(
                f"Failed to load initial facts: {facts_result}",
                exc_info=isinstance(facts_result, Exception),
                extra=log_extra,
            )
            self.prompt_context_cache.require_fact_refresh()  # Ensure retry
        elif isinstance(facts_result, list) and all(
            isinstance(f, UserFactRead) for f in facts_result
        ):
            try:
                loaded_fact_texts = [
                    fact.fact for fact in facts_result if hasattr(fact, "fact")
                ]
                logger.info(
                    f"Successfully loaded {len(loaded_fact_texts)} initial facts.",
                    extra=log_extra,
                )
            except Exception as e:
                logger.error(
                    f"Error processing loaded facts: {e}",
                    exc_info=True,
                    extra=log_extra,
                )
                self.prompt_context_cache.require_fact_refresh()  # Ensure retry on processing error
        else:
            logger.info("No initial facts found or unexpected format.", extra=log_extra)
        # Update cache (even if None, resets flag)
        self.prompt_context_cache.update_facts(loaded_fact_texts)

    # --- MODIFIED: Prompt Modifier ---
    async def _add_system_prompt_modifier(
        self,
        state: AssistantState,  # state still contains filtered messages thanks to reducer
    ) -> List[BaseMessage]:
        """
        Dynamically creates the SystemMessage using the shared cache,
        refreshing data via REST if flags indicate necessity.
        """
        try:
            user_id_int = int(self.user_id)
        except ValueError:
            logger.error(
                f"Invalid user_id format in modifier: {self.user_id}. Cannot refresh data."
            )
            user_id_int = None

        log_extra = {"assistant_id": self.assistant_id, "user_id": self.user_id}

        refresh_tasks = []

        # --- Check if Refresh Needed (using shared cache flags) --- #
        current_messages = state.get("messages", [])
        if current_messages:
            last_message = current_messages[-1]
            if (
                isinstance(last_message, ToolMessage)
                and getattr(last_message, "name", None) == FACT_SAVE_TOOL_NAME
                and last_message.content == FACT_SAVE_SUCCESS_MESSAGE
            ):
                logger.info(
                    "Fact save tool used, triggering fact refresh via cache flag.",
                    extra=log_extra,
                )
                self.prompt_context_cache.require_fact_refresh()  # Set flag on shared cache

        if self.prompt_context_cache.needs_summary_refresh and user_id_int is not None:
            logger.info("Scheduling summary refresh for cache...", extra=log_extra)
            refresh_tasks.append(
                self.rest_client.get_user_summary(
                    user_id=user_id_int, secretary_id=self.assistant_id_uuid
                )
            )
        else:
            refresh_tasks.append(None)  # Placeholder

        if self.prompt_context_cache.needs_fact_refresh and user_id_int is not None:
            logger.info("Scheduling fact refresh for cache...", extra=log_extra)
            refresh_tasks.append(self.rest_client.get_user_facts(user_id=user_id_int))
        else:
            refresh_tasks.append(None)  # Placeholder

        # --- Execute Refresh Tasks and Update Cache --- #
        if any(task is not None for task in refresh_tasks):
            results = await asyncio.gather(
                *[task for task in refresh_tasks if task is not None],
                return_exceptions=True,
            )
            result_idx = 0

            # Process Summary Result (if refresh was scheduled)
            if refresh_tasks[0] is not None:
                summary_result = results[result_idx]
                refreshed_summary = None
                if isinstance(summary_result, Exception):
                    logger.error(
                        f"Failed to refresh summary: {summary_result}",
                        exc_info=True,
                        extra=log_extra,
                    )
                    self.prompt_context_cache.require_summary_refresh()  # Ensure retry
                elif summary_result and hasattr(summary_result, "summary_text"):
                    refreshed_summary = summary_result.summary_text
                    logger.info("Summary cache refreshed.", extra=log_extra)
                else:
                    logger.info("No summary found during refresh.", extra=log_extra)
                # Update cache (even if None, resets flag)
                self.prompt_context_cache.update_summary(refreshed_summary)
                result_idx += 1

            # Process Facts Result (MODIFIED to handle UserFactRead)
            if refresh_tasks[1] is not None:
                facts_result = results[result_idx]
                refreshed_fact_texts: Optional[List[str]] = None
                if isinstance(facts_result, Exception):
                    logger.error(
                        f"Failed to refresh facts: {facts_result}",
                        exc_info=True,
                        extra=log_extra,
                    )
                    self.prompt_context_cache.require_fact_refresh()  # Ensure retry
                elif isinstance(facts_result, list) and all(
                    isinstance(f, UserFactRead) for f in facts_result
                ):
                    try:
                        refreshed_fact_texts = [
                            fact.fact for fact in facts_result if hasattr(fact, "fact")
                        ]
                        logger.info(
                            f"Fact cache refreshed. Cached {len(refreshed_fact_texts)} facts.",
                            extra=log_extra,
                        )
                    except Exception as e:
                        logger.error(
                            f"Error processing refreshed facts: {e}",
                            exc_info=True,
                            extra=log_extra,
                        )
                        self.prompt_context_cache.require_fact_refresh()  # Ensure retry
                else:
                    logger.warning(
                        "No facts found or unexpected format during refresh.",
                        extra=log_extra,
                    )
                # Update cache with the list of fact *strings*
                self.prompt_context_cache.update_facts(refreshed_fact_texts)

        # --- Format System Prompt (using shared cache data) --- #
        facts_str = (
            "\n".join(f"- {fact}" for fact in self.prompt_context_cache.facts)
            if self.prompt_context_cache.facts
            else "Нет известных фактов."
        )
        summary_str = (
            self.prompt_context_cache.summary
            if self.prompt_context_cache.summary
            else "Нет предыдущей истории диалога (саммари)."
        )

        try:
            formatted_prompt = self.system_prompt_template.format(
                summary_previous=summary_str, user_facts=facts_str
            )
        except KeyError as e:
            logger.error(
                f"Missing key in system_prompt_template: {e}. Using template as is.",
                extra=log_extra,
            )
            formatted_prompt = self.system_prompt_template  # Fallback

        system_message = SystemMessage(content=formatted_prompt)

        # --- Combine with filtered history --- #
        final_messages: List[BaseMessage] = [system_message] + list(current_messages)

        try:
            total_tokens = count_tokens(final_messages)
            await log_messages_to_file(
                assistant_id=self.assistant_id,
                user_id=self.user_id,
                messages=final_messages,
                total_tokens=total_tokens,
                context_limit=self.max_tokens,
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
        log_extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
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
                f"Mismatch user_id: assistant instance for {self.user_id} received message for {user_id}"
            )
            raise ValueError("User ID mismatch")

        # Common logging context
        combined_log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": self.user_id,
        }
        if log_extra:
            combined_log_extra.update(log_extra)

        # Получение глобальных настроек для создания AssistantState
        global_settings = await self.rest_client.get_global_settings()

        try:
            # Формируем AssistantState для графа
            initial_state = AssistantState(
                messages=[message],  # Входящее сообщение
                user_id=user_id,
                assistant_id=self.assistant_id,
                llm_context_size=self.max_tokens,
                triggered_event=None,  # Если это обычное сообщение, а не триггер
                log_extra=combined_log_extra,
                initial_message_id=None,  # ID сообщения будет установлен узлом save_input_message_node
                current_summary_content=None,  # Будет загружено графом
                newly_summarized_message_ids=None,
                user_facts=None,  # Будет загружено графом
            )

            # Запускаем граф
            try:
                final_state = await self.compiled_graph.ainvoke(
                    input=dict(initial_state),
                    config=None,  # Чекпоинтер больше не используется
                )

                if not final_state or "messages" not in final_state:
                    raise MessageProcessingError(
                        "Graph execution finished but final state is missing or invalid.",
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
                            f"Successfully processed message. Response: {ai_response[:100]}...",
                            extra=combined_log_extra,
                        )
                    elif isinstance(last_message, ToolMessage):
                        logger.info(
                            "Processing finished with a ToolMessage (likely from fact save/reminder trigger processing). No response sent to user.",
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
                            f"Failed to update message status after error: {update_error}",
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
        """Cleans up resources, like closing the REST client session."""
        if self.rest_client:
            await self.rest_client.close_session()
            logger.info(
                "REST client session closed.", extra={"assistant_id": self.assistant_id}
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
