# assistant_service/src/assistants/langgraph/langgraph_assistant.py

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Project specific imports
from assistants.base_assistant import BaseAssistant  # Absolute import from src
from assistants.langgraph.graph_builder import build_full_graph
from assistants.langgraph.state import AssistantState, update_dialog_stack

# Import logging utility
from assistants.langgraph.utils.logging_utils import log_messages_to_file

# Import token counter utility
from assistants.langgraph.utils.token_counter import count_tokens
from config.settings import settings  # To get API keys if not in assistant config

# Base classes and core types
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

# LangGraph components
from langgraph.checkpoint.base import (  # Import needed for checkpointer
    BaseCheckpointSaver,
)
from langgraph.graph.state import CompiledGraph
from langgraph.prebuilt import create_react_agent  # Import create_react_agent
from services.rest_service import RestServiceClient  # Import RestServiceClient
from utils.error_handler import (
    AssistantError,
    MessageProcessingError,
    handle_assistant_error,
)

from shared_models import QueueTrigger, TriggerType

from .constants import (
    FACT_SAVE_SUCCESS_MESSAGE,
    FACT_SAVE_TOOL_NAME,
    SYSTEM_PROMPT_NAME,
    USER_FACTS_NAME,
)

logger = logging.getLogger(__name__)


class LangGraphAssistant(BaseAssistant):
    """
    Assistant implementation using LangGraph with a custom graph structure
    similar to the old BaseLLMChat, supporting checkpointing for memory.
    Handles fact caching internally.
    """

    compiled_graph: CompiledGraph
    agent_runnable: Any
    tools: List[Tool]
    rest_client: RestServiceClient
    checkpointer: BaseCheckpointSaver
    llm: ChatOpenAI

    cached_facts: Optional[List[str]] = None
    needs_fact_refresh: bool = True

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: Dict,
        tools: List[Tool],  # Receive initialized tools
        user_id: str,  # Receive user_id
        checkpointer: BaseCheckpointSaver,  # Require checkpointer
        rest_client: RestServiceClient,  # Add rest_client parameter
        **kwargs,
    ):
        """
        Initializes the LangGraphAssistant with pre-initialized tools and checkpointing.

        Args:
            assistant_id: Unique identifier for the assistant instance.
            name: Name of the assistant.
            config: Dictionary containing configuration parameters.
                    Expected keys: 'model_name', 'temperature', 'api_key' (optional),
                                   'system_prompt', 'timeout' (optional, default 60).
            tools: List of initialized Langchain Tool instances.
            user_id: The ID of the user associated with this assistant instance.
            checkpointer: Checkpointer instance for state persistence.
            rest_client: REST Service client instance.
            **kwargs: Additional keyword arguments.
        """
        raw_tool_definitions = config.get(
            "tools", []
        )  # Get raw defs if they exist in config, else empty
        super().__init__(assistant_id, name, config, raw_tool_definitions, **kwargs)

        # Store pre-initialized tools and user_id
        self.tools = tools
        self.user_id = user_id  # Store user_id if needed by other methods
        self.checkpointer = checkpointer
        self.rest_client = rest_client  # Store the rest_client
        self.timeout = self.config.get("timeout", 60)  # Default timeout 60 seconds
        self.system_prompt = self.config["system_prompt"]
        self.max_tokens = self.config.get("max_tokens", 2500)

        # --- Ensure internal fact refresh flag is set --- #
        self.needs_fact_refresh = True
        self.cached_facts = None
        # ------------------------------------------------- #

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
                run_node_fn=self._run_assistant_node,
                tools=self.tools,
                checkpointer=self.checkpointer,
                summary_llm=self.llm,  # Pass the initialized main LLM as the summary LLM
            )

            logger.info(
                "LangGraphAssistant initialized (internal fact caching)",
                extra={
                    "assistant_id": self.assistant_id,
                    "assistant_name": self.name,
                    "user_id": self.user_id,
                    "tools_count": len(self.tools),
                    "timeout": self.timeout,
                    "rest_client_provided": self.rest_client is not None,
                    "initial_needs_fact_refresh": self.needs_fact_refresh,
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
        temperature = self.config.get("temperature", 0.7)
        api_key = self.config.get("api_key", settings.OPENAI_API_KEY)

        if not api_key:
            raise ValueError(
                f"OpenAI API key is not configured for assistant {self.assistant_id}."
            )

        logger.debug(
            "Initializing LLM",
            extra={
                "assistant_id": self.assistant_id,
                "model_name": model_name,
                "temperature": temperature,
            },
        )
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
        )

    def _create_agent_runnable(self) -> Any:
        """Creates the core agent runnable (e.g., using create_react_agent).

        Ensures the system prompt is bound to the LLM before passing to create_react_agent.
        """
        try:
            # Pass the ORIGINAL LLM to create_react_agent
            # System prompt will be handled by the function passed to the 'prompt' parameter
            return create_react_agent(
                self.llm,  # Pass original LLM
                self.tools,
                # Use the 'prompt' parameter as confirmed by experiment
                prompt=self._add_system_prompt_modifier,
            )
        except Exception as e:
            raise AssistantError(
                f"Failed to create agent runnable: {str(e)}", self.name
            ) from e

    async def _add_system_prompt_modifier(
        self, state: AssistantState, used_for_token_count: bool = False
    ) -> List[BaseMessage]:
        """Handles system prompt and user fact injection before LLM call.

        Checks if facts need refresh, fetches/uses cached facts,
        and constructs the final message list with Prompt, Facts, and History.
        The ordering of special messages (prompt, facts, summary) is now primarily
        handled by the custom_message_reducer.
        Uses self.user_id and self.rest_client directly.
        """
        user_id = self.user_id
        log_extra = {"assistant_id": self.assistant_id, "user_id": user_id}
        logger.debug(
            "Entering _add_system_prompt_modifier (summary placement handled by reducer)",
            extra=log_extra,
        )

        current_messages = state.get("messages", [])

        if current_messages:
            last_message = current_messages[-1]
            if (
                isinstance(last_message, ToolMessage)
                and getattr(last_message, "name", None) == FACT_SAVE_TOOL_NAME
                and last_message.content == FACT_SAVE_SUCCESS_MESSAGE
            ):
                logger.info("Fact save detected, triggering refresh.", extra=log_extra)
                self.needs_fact_refresh = True

        should_fetch = self.needs_fact_refresh or self.cached_facts is None
        fetched_facts: Optional[List[str]] = None

        if should_fetch:
            logger.debug("Fetching/refreshing user facts.", extra=log_extra)
            try:
                fetched_facts = await self.rest_client.get_user_facts(user_id=user_id)
                if isinstance(fetched_facts, list):
                    self.cached_facts = fetched_facts
                    logger.info(
                        f"Successfully fetched and cached {len(self.cached_facts)} facts.",
                        extra=log_extra,
                    )
                self.needs_fact_refresh = False
            except Exception as e:
                logger.exception(
                    "Failed to fetch user facts. Using potentially stale cache or empty list.",
                    extra=log_extra,
                    exc_info=True,
                )
                if self.cached_facts is None:
                    self.cached_facts = []
        else:
            logger.debug("Using cached user facts.", extra=log_extra)

        facts_message_content = "No facts available."
        if self.cached_facts:
            facts_list_str = "\n".join([f"- {fact}" for fact in self.cached_facts])
            facts_message_content = f"Facts about the user:\n{facts_list_str}"

        facts_system_message = SystemMessage(
            content=facts_message_content, name=USER_FACTS_NAME
        )

        system_prompt_message = SystemMessage(
            content=self.system_prompt, name=SYSTEM_PROMPT_NAME
        )

        history_messages = []
        for msg in current_messages:
            # Skip system prompts, facts by the reducer
            if isinstance(msg, SystemMessage):
                msg_name = getattr(msg, "name", None)
                if msg_name in [
                    SYSTEM_PROMPT_NAME,
                    USER_FACTS_NAME,
                ]:
                    continue

            # If it's not a special message to be skipped, add it to history
            history_messages.append(msg)

        # The reducer will place prompt and facts correctly.
        # This modifier now only needs to provide the *base* for the LLM call:
        # Prompt, Facts, and the filtered History.
        final_messages = [system_prompt_message, facts_system_message]

        final_messages.extend(history_messages)  # Add the filtered history

        logger.debug(
            f"Modifier returning {len(final_messages)} messages for LLM (reducer handles final order).",
            extra=log_extra,
        )

        if not used_for_token_count:
            try:
                total_tokens = count_tokens(final_messages)
                llm_context_size = self.max_tokens
                await log_messages_to_file(
                    assistant_id=self.assistant_id,
                    user_id=user_id,
                    messages=final_messages,
                    total_tokens=total_tokens,
                    context_limit=llm_context_size,
                    step_name="Modifier Output (Corrected Order)",  # Updated step name
                )
            except Exception as e:
                logger.error(
                    f"!!! Failed to call log_messages_to_file: {e}",
                    exc_info=True,
                    extra=log_extra,
                )
        # --- End File Logging --- #

        return final_messages

    async def _run_assistant_node(self, state: AssistantState) -> Dict[str, Any]:
        """Runs the agent logic.

        - Calculates and updates `current_token_count` BEFORE invoking the LLM.
        - Checks for fact tool success to set refresh flag.
        - Invokes the core agent runnable.
        - Returns the result, including the calculated token count.
        """
        start_node_time = time.perf_counter()
        user_id = self.user_id
        dialog_stack = state.get("dialog_state")
        current_dialog = dialog_stack[-1] if dialog_stack else "unknown"
        log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": user_id,
            "current_dialog_state": current_dialog,
        }
        logger.debug("Entering _run_assistant_node", extra=log_extra)

        current_messages = state.get("messages", [])
        if current_messages:
            last_message = current_messages[-1]
            if (
                isinstance(last_message, ToolMessage)
                and getattr(last_message, "name", None) == FACT_SAVE_TOOL_NAME
                and last_message.content == FACT_SAVE_SUCCESS_MESSAGE
            ):
                logger.info(
                    "Successful fact save detected in _run_assistant_node. Setting refresh flag.",
                    extra=log_extra,
                )
                self.needs_fact_refresh = True  # SET THE FLAG HERE

        triggered_event = state.get("triggered_event")
        messages_for_agent = list(
            state["messages"]
        )  # Use original state messages for agent input
        state_update_from_trigger = {}

        if triggered_event:
            logger.info(
                "Processing triggered event in assistant node",
                extra={
                    **log_extra,
                    "event_type": triggered_event.trigger_type,
                    "event_payload": triggered_event.payload,
                },
            )
            trigger_message_content = triggered_event.payload.get(
                "message", "Trigger event received."
            )
            messages_for_agent.append(HumanMessage(content=trigger_message_content))
            state_update_from_trigger = {"triggered_event": None}
            logger.debug(
                "Appended trigger event message to history (for agent input)",
                extra=log_extra,
            )

        if not messages_for_agent or len(messages_for_agent) == 0:
            logger.warning("Assistant node called with empty messages", extra=log_extra)

        # for exact token count use _add_system_prompt_modifier
        try:
            messages_to_count = await self._add_system_prompt_modifier(state)
            calculated_token_count = count_tokens(messages_to_count)
            logger.debug(
                f"Calculated token count BEFORE invoke: {calculated_token_count}",
                extra=log_extra,
            )
        except Exception as count_exc:
            logger.exception(
                "Error calculating token count before invoke",
                extra=log_extra,
                exc_info=True,
            )
            calculated_token_count = state.get(
                "current_token_count"
            )  # Fallback to potentially stale count

        # --- End Token Calculation --- #

        agent_input = {
            "messages": messages_for_agent
        }  # Input for agent remains the same as before
        logger.debug(
            f"Messages passed to agent runnable input (count may differ due to modifier): {len(agent_input['messages'])}",
            extra=log_extra,
        )

        logger.debug("Invoking agent runnable", extra=log_extra)
        try:
            agent_output = await self.agent_runnable.ainvoke(agent_input)
            # IMPORTANT: The agent_output["messages"] contains only the *new* messages from the LLM/tools.
            # It does NOT include the history that was passed in.
            # To update the state correctly, we need to combine the existing state messages
            # with the new messages from the agent output.
            # LangGraph's add_messages reducer handles this automatically when we return {"messages": new_messages}.
            new_messages = agent_output.get("messages", [])

            final_update = {
                "messages": new_messages,  # Let add_messages handle merging
                "current_token_count": calculated_token_count,  # Add the calculated count HERE
                **state_update_from_trigger,
                "dialog_state": agent_output.get(
                    "dialog_state", state.get("dialog_state")
                ),
            }
            final_update["last_activity"] = datetime.now(timezone.utc)
            node_duration = time.perf_counter() - start_node_time
            logger.debug(
                f"_run_assistant_node completed in {node_duration:.4f}s, returning {len(new_messages)} new messages. Updated token count to {calculated_token_count}",
                extra=log_extra,
            )
            return final_update
        except Exception as e:
            node_duration = time.perf_counter() - start_node_time
            logger.exception(
                f"Error during agent invocation in _run_assistant_node ({node_duration:.4f}s)",
                extra=log_extra,
                exc_info=True,
            )
            error_message = SystemMessage(
                content=f"Error processing request: {e}", name="error_message"
            )
            # Also return the calculated token count even on error, might be useful for debugging
            return {
                "messages": [error_message],  # Let add_messages handle merging
                "current_token_count": calculated_token_count,
                "dialog_state": update_dialog_stack(
                    ["error"], state.get("dialog_state")
                ),
                "last_activity": datetime.now(timezone.utc),
                **state_update_from_trigger,
            }

    # --- End Graph Node Definitions ---

    async def process_message(
        self,
        message: Optional[BaseMessage],
        user_id: str,
        triggered_event: QueueTrigger = None,  # Add triggered_event parameter
    ) -> str:
        """
        Processes an incoming message or event using the compiled LangGraph,
        handling state persistence via the checkpointer.
        """
        thread_id = f"user_{user_id}_assistant_{self.assistant_id}"
        start_time = time.perf_counter()  # Start timer
        log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": user_id,
            "message_type": type(message).__name__ if message else "None",
            "triggered_event_type": triggered_event.trigger_type
            if triggered_event
            else None,
        }
        logger.debug(f"Entering process_message", extra=log_extra)

        # Ensure checkpointer is available
        if not self.checkpointer:
            logger.error("Checkpointer is not configured.", extra=log_extra)
            raise AssistantError("Checkpointer is not configured.", self.name)

        # Create a configuration dictionary for the specific user thread
        config = {"configurable": {"thread_id": thread_id}}

        # --- Input Preparation ---
        input_messages = []
        if message:
            input_messages.append(message)
            logger.debug(
                "Processing standard message",
                extra={**log_extra, "message_type": type(message).__name__},
            )

        # Prepare the input dictionary for ainvoke
        # Include the new messages AND essential initial state values
        graph_input: Dict[str, Any] = {
            "messages": input_messages,  # New messages to be processed
            "user_id": user_id,  # Always provide user_id
            # TODO: Get llm_context_size from config properly later
            "llm_context_size": self.config.get(
                "llm_context_size", 2600
            ),  # Example default
            # Potentially other initial defaults if needed, but state defaults cover most
        }

        # Add triggered event if present
        if triggered_event:
            graph_input["triggered_event"] = triggered_event
            logger.debug(
                "Passing triggered event in graph input state",
                extra={**log_extra, "event_type": triggered_event.trigger_type},
            )
        elif not message and not triggered_event:
            logger.warning(
                "process_message called with no message or event", extra=log_extra
            )
            return ""

        # --- Graph Invocation ---
        final_state = None
        try:
            # Pass the merged input. LangGraph loads checkpoint and merges this input over it.
            # Keys in graph_input (like messages) overwrite loaded state.
            # Keys not in graph_input (like previous history if checkpoint exists) are kept.
            final_state = await self.compiled_graph.ainvoke(graph_input, config=config)

            end_time = time.perf_counter()
            duration = end_time - start_time
            # Safely get the final dialog state for logging
            final_dialog_stack = (
                final_state.get("dialog_state") if final_state else None
            )
            final_dialog = final_dialog_stack[-1] if final_dialog_stack else "unknown"
            logger.info(
                f"Graph execution finished in {duration:.4f}s",
                extra={
                    **log_extra,
                    "final_dialog_state": final_dialog,
                },  # Use safe value
            )

        # --- Error Handling ---
        except asyncio.TimeoutError:
            duration = time.perf_counter() - start_time
            logger.error(
                f"Graph execution timed out after {duration:.4f}s", extra=log_extra
            )
            # Update state in checkpoint to reflect timeout? Requires checkpointer access here.
            # Maybe return a specific timeout message
            return "Assistant timed out."
        except MessageProcessingError as e:
            # This indicates an error within our processing logic (nodes, etc.)
            duration = time.perf_counter() - start_time
            # Safely get final dialog state for logging here too
            final_dialog_stack_mpe = (
                final_state.get("dialog_state") if final_state else None
            )
            final_dialog_mpe = (
                final_dialog_stack_mpe[-1] if final_dialog_stack_mpe else "unknown"
            )
            logger.error(
                f"Message processing error after {duration:.4f}s: {e}",
                extra={
                    **log_extra,
                    "final_dialog_state": final_dialog_mpe,
                },  # Use safe value
                exc_info=True,
            )
            # Potentially update state to 'error' in checkpoint
            return f"Error processing message: {e}"
        except Exception as e:
            # Catch-all for unexpected errors during graph execution
            duration = time.perf_counter() - start_time
            # Safely get final dialog state for logging, even if final_state is None or empty
            final_dialog_stack_exc = (
                final_state.get("dialog_state") if final_state else None
            )
            final_dialog_exc = (
                final_dialog_stack_exc[-1] if final_dialog_stack_exc else "unknown"
            )

            logger.exception(
                f"Unexpected error during graph execution after {duration:.4f}s: {e}",
                extra={
                    **log_extra,
                    "final_dialog_state": final_dialog_exc,
                },  # Use safe value again
                exc_info=True,
            )
            # Potentially update state to 'error' in checkpoint
            return f"An unexpected error occurred: {e}"

        # --- Response Extraction ---
        if final_state and final_state.get("messages"):
            last_message = final_state["messages"][-1]
            if isinstance(last_message, AIMessage):
                response_content = last_message.content
                end_time = time.perf_counter()  # End timer
                duration = end_time - start_time
                log_extra["duration_ms"] = round((duration) * 1000)
                logger.info(
                    f"Successfully processed message for user {user_id}",
                    response_preview=f"{str(response_content)[:100]}...",
                    extra=log_extra,
                )
                return response_content
            else:
                # The graph ended on a non-AI message (ToolMessage, SystemMessage, HumanMessage?)
                # This might indicate an issue or an unexpected end state.
                logger.warning(
                    f"Graph ended with non-AIMessage: {type(last_message).__name__}",
                    extra=log_extra,
                )
                # Return empty string or a default message?
                return ""  # Or "Processing complete."
        else:
            logger.warning(
                "Graph execution finished with no messages in final state",
                extra=log_extra,
            )
            return ""  # No response generated

        """Retrieves the message history for the user."""
        thread_id = f"user_{user_id}_assistant_{self.assistant_id}"
        try:
            config = {"configurable": {"thread_id": thread_id}}
            # Get the state WITHOUT invoking the graph
            # IMPORTANT: This retrieves the raw persisted state.
            # It will NOT contain facts/prompt added dynamically by the modifier.
            state_snapshot = await self.checkpointer.aget(config)
            # state = await self.compiled_graph.aget_state(config) # This might run parts of the graph?
            # return state.messages if state else [] # Incorrect if using raw checkpoint
            if (
                state_snapshot
                and state_snapshot.get("values")
                and "messages" in state_snapshot["values"]
            ):
                return state_snapshot["values"]["messages"]
            else:
                logger.debug(
                    f"No message history found in checkpoint for thread {thread_id}",
                    extra={"user_id": user_id, "assistant_id": self.assistant_id},
                )
                return []
        except Exception as e:
            logger.exception(
                f"Error retrieving history from checkpointer for thread {thread_id}: {e}",
                extra={"user_id": user_id, "assistant_id": self.assistant_id},
                exc_info=True,
            )
            return []

    async def close(self):
        """Placeholder for cleanup, if needed."""
        logger.info(f"Closing LangGraphAssistant {self.assistant_id}")


# TODO:
# 1. Add proper error handling within the nodes (e.g., for API errors from LLM/Tools).
# 2. Implement timeout mechanism within the nodes or graph execution.
# 3. Consider adding state transitions for 'error' and 'timeout' in dialog_state.
# 4. Refine how system prompts are handled (ensure they are always first message).
# 5. Test checkpointing and state recovery thoroughly.
# 6. Add logging for state transitions.
