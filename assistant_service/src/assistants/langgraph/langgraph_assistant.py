# assistant_service/src/assistants/langgraph/langgraph_assistant.py

import asyncio
import logging
import time  # Import time module
from datetime import datetime, timezone  # Import timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

# Project specific imports
# Change import path for BaseAssistant to go up one level
# from assistants.base_assistant import BaseAssistant
from assistants.base_assistant import BaseAssistant  # Absolute import from src

# Import the new graph builder function using absolute path from src
# Need to adjust relative path for graph_builder and state now
# from assistants.langgraph.graph_builder import build_base_graph
# from assistants.langgraph.state import AssistantState, update_dialog_stack
from assistants.langgraph.graph_builder import build_full_graph  # Updated import
from assistants.langgraph.state import (  # Absolute import from src
    AssistantState,
    update_dialog_stack,
)

# --- Tool Imports ---
# Import specific tool implementation classes directly for now
# TODO: Refactor using a ToolFactory later
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
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.graph.state import CompiledGraph
from langgraph.prebuilt import create_react_agent  # Import create_react_agent
from langgraph.prebuilt import ToolNode, tools_condition
from services.rest_service import RestServiceClient  # Import RestServiceClient

# --- End Tool Imports ---
# Need to adjust relative path for utils
# from utils.error_handler import handle_assistant_error  # Import error handlers
# from utils.error_handler import AssistantError, MessageProcessingError
from utils.error_handler import handle_assistant_error  # Absolute import from src
from utils.error_handler import (  # Absolute import from src
    AssistantError,
    MessageProcessingError,
)

# Need to adjust relative path for shared_models
# from shared_models import TriggerType
from shared_models import TriggerType  # Absolute import from src

# Remove TypedDict if only used for AssistantState
# from typing_extensions import TypedDict


logger = logging.getLogger(__name__)

# --- State Definition (REMOVED - Now in state.py) ---


class LangGraphAssistant(BaseAssistant):
    """
    Assistant implementation using LangGraph with a custom graph structure
    similar to the old BaseLLMChat, supporting checkpointing for memory.
    """

    compiled_graph: CompiledGraph
    agent_runnable: Any  # The agent created by create_react_agent
    # Define tools attribute directly
    tools: List[Tool]
    rest_client: RestServiceClient  # Add rest_client attribute

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: Dict,
        # tool_definitions: List[Dict], -> Replaced by tools
        tools: List[Tool],  # Receive initialized tools
        user_id: str,  # Receive user_id
        checkpointer: BaseCheckpointSaver,  # Require checkpointer
        rest_client: RestServiceClient,  # Add rest_client parameter
        # tool_factory: ToolFactory, -> Removed
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
        # Initialize BaseAssistant first
        # Note: BaseAssistant still saves raw tool_definitions if the base init is kept unchanged
        # We might want to adjust BaseAssistant later if needed.
        # For now, pass an empty list or config['tools'] to BaseAssistant
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
        self.system_prompt = self.config.get(
            "system_prompt", "You are a helpful assistant."
        )  # Default prompt

        try:
            # 1. Initialize LLM
            self.llm = self._initialize_llm()

            # 2. Initialize Langchain Tools -> REMOVED (Tools are passed in)

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
                rest_client=self.rest_client,
                system_prompt_text=self.system_prompt,  # Pass system prompt text
            )

            logger.info(
                "LangGraphAssistant initialized",  # Removed (Using graph_builder)
                extra={
                    "assistant_id": self.assistant_id,
                    "assistant_name": self.name,
                    "user_id": self.user_id,
                    "tools_count": len(self.tools),
                    "timeout": self.timeout,
                    "rest_client_provided": self.rest_client is not None,
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
        """Creates the core agent runnable (e.g., using create_react_agent)."""
        try:
            # Pass system prompt here if the agent creation supports it
            # Note: create_react_agent in newer versions might take messages including system prompt directly
            # For now, assuming it uses a prompt argument or infers from LLM binding
            # Let's use a simple approach: bind the system message to the LLM if possible,
            # or rely on create_react_agent's default prompt creation which uses system messages.
            # We need to ensure the system message IS part of the history passed to the agent runnable.

            # Correct way is often to pass messages including system to invoke,
            # but create_react_agent itself sets up the prompt internally based on messages.
            # Let's rely on create_react_agent for now. System message will be added to state.
            # Use self.tools which are now passed during initialization
            return create_react_agent(
                self.llm,
                self.tools,
                # messages_modifier=... # Optional: If specific prompt engineering needed
            )
        except Exception as e:
            raise AssistantError(
                f"Failed to create agent runnable: {str(e)}", self.name
            ) from e

    # --- Graph Node Definitions ---

    async def _run_assistant_node(self, state: AssistantState) -> dict:
        """The node that runs the core agent logic (using create_react_agent runnable).
        Also handles triggered events by adding a message to the history.
        """
        start_node_time = time.perf_counter()  # Start node timer

        # Safer way to get the current dialog state for logging
        dialog_stack = state.get("dialog_state")
        current_dialog = dialog_stack[-1] if dialog_stack else "unknown"

        log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": state.get("user_id"),  # Get user_id from state
            "current_dialog_state": current_dialog,  # Use the safely retrieved value
        }
        logger.debug("Entering _run_assistant_node", extra=log_extra)

        # Check for triggered event FIRST
        triggered_event = state.get("triggered_event")
        messages_for_agent = list(state["messages"])  # Create a mutable copy
        state_update_from_trigger = {}

        if triggered_event:
            logger.info(
                "Processing triggered event in assistant node",
                extra={**log_extra, "event_type": triggered_event.get("type")},
            )
            # Add a message representing the trigger to the history
            # Example: Use ToolMessage for structure if appropriate
            trigger_message_content = triggered_event.get(
                "content", "A scheduled event was triggered."
            )
            # Use a specific tool_call_id or name to identify trigger messages?
            trigger_tool_id = triggered_event.get("tool_call_id", "event_trigger_0")
            messages_for_agent.append(
                ToolMessage(
                    content=trigger_message_content, tool_call_id=trigger_tool_id
                )
            )
            # Clear the triggered event from the state after processing
            state_update_from_trigger = {"triggered_event": None}
            logger.debug("Appended trigger event message to history", extra=log_extra)

        if not messages_for_agent:
            logger.warning("Assistant node called with empty messages", extra=log_extra)
            # Decide how to handle this - maybe return an empty response or error?
            # For now, let it proceed, agent_runnable might handle it.
            pass  # Or return {"messages": []} ?

        # Prepare state for the agent runnable
        # The agent runnable expects a dictionary, usually {'messages': [...]}
        agent_input = {"messages": messages_for_agent}

        # Log the exact messages being sent to the agent runnable
        logger.debug(
            f"Messages passed to agent runnable: {agent_input['messages']}",
            extra=log_extra,
        )

        logger.debug("Invoking agent runnable", extra=log_extra)
        try:
            # Invoke the core agent logic
            agent_output = await self.agent_runnable.ainvoke(agent_input)

            # Agent output is typically a dict containing the new messages
            # Example: {"messages": [AIMessage(...)]} or {"messages": [ToolMessage(...)]}
            new_messages = agent_output.get("messages", [])

            # Construct the full updated message list for the state
            # Since we use set_messages, we need to return the complete history
            full_updated_messages = messages_for_agent + new_messages

            # Combine agent output with any updates from trigger processing
            # Replace the potentially partial 'messages' from agent_output with the full list
            final_update = {
                **agent_output,  # Keep other potential fields from agent_output
                "messages": full_updated_messages,  # Overwrite with the full list
                **state_update_from_trigger,
            }

            # Update last activity time
            final_update["last_activity"] = datetime.now(timezone.utc)

            node_duration = time.perf_counter() - start_node_time
            logger.debug(
                f"_run_assistant_node completed in {node_duration:.4f}s, returning {len(full_updated_messages)} messages",
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
            # Return state update indicating error, including the original messages + error message
            error_message = SystemMessage(
                content=f"Error processing request: {e}", name="error_message"
            )
            # Return the state as it was, plus the error message
            return {
                "messages": messages_for_agent
                + [error_message],  # Keep history + add error
                "dialog_state": update_dialog_stack(
                    ["error"], state.get("dialog_state")
                ),  # Push error state
                "last_activity": datetime.now(timezone.utc),
                **state_update_from_trigger,  # Include trigger update
            }

    # --- End Graph Node Definitions ---

    async def process_message(
        self,
        message: Optional[BaseMessage],
        user_id: str,
        triggered_event: Optional[dict] = None,  # Add triggered_event parameter
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
            "triggered_event_type": triggered_event.get("type")
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
            # Add llm_context_size if available on the assistant instance
            # This assumes llm_context_size is set during assistant init or config
            # TODO: Get llm_context_size from config properly later
            "llm_context_size": self.config.get(
                "llm_context_size", 4096
            ),  # Example default
            # Potentially other initial defaults if needed, but state defaults cover most
        }

        # Add triggered event if present
        if triggered_event:
            graph_input["triggered_event"] = triggered_event
            logger.debug(
                "Passing triggered event in graph input state",
                extra={**log_extra, "event_type": triggered_event.get("type")},
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

    async def get_history(self, user_id: str) -> List[BaseMessage]:
        """Retrieves the message history for the user."""
        thread_id = f"user_{user_id}_assistant_{self.assistant_id}"
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = await self.compiled_graph.aget_state(config)
            return state.messages if state else []
        except Exception as e:
            logger.exception(
                f"Error retrieving history for thread {thread_id}: {e}", exc_info=True
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
