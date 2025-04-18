# assistant_service/src/assistants/langgraph_assistant.py

import asyncio
import logging
import time  # Import time module
from datetime import datetime, timezone  # Import timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

# Project specific imports
from assistants.base_assistant import BaseAssistant

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
from typing_extensions import TypedDict

# --- End Tool Imports ---
from utils.error_handler import handle_assistant_error  # Import error handlers
from utils.error_handler import AssistantError, MessageProcessingError

from shared_models import TriggerType

logger = logging.getLogger(__name__)

# --- State Definition (copied and adapted from llm_chat.py) ---


def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        # Ensure we don't pop from an empty list or the initial 'idle'
        if len(left) > 1:
            return left[:-1]
        return left  # Return as is if only 'idle' or empty
    return left + [right]


class AssistantState(TypedDict):
    """State for the assistant, including messages and dialog tracking."""

    messages: Annotated[list[AnyMessage], add_messages]
    user_id: Optional[str]  # Keep track of the user ID
    # Add field for external trigger events like reminders
    triggered_event: Optional[dict] = None

    dialog_state: Annotated[
        # Add more states if needed, keep simple for now
        list[Literal["idle", "processing", "waiting_for_tool", "error", "timeout"]],
        update_dialog_stack,
    ]
    last_activity: datetime  # Track last activity for timeout purposes


# --- End State Definition ---


class LangGraphAssistant(BaseAssistant):
    """
    Assistant implementation using LangGraph with a custom graph structure
    similar to the old BaseLLMChat, supporting checkpointing for memory.
    """

    compiled_graph: CompiledGraph
    agent_runnable: Any  # The agent created by create_react_agent
    # Define tools attribute directly
    tools: List[Tool]

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: Dict,
        # tool_definitions: List[Dict], -> Replaced by tools
        tools: List[Tool],  # Receive initialized tools
        user_id: str,  # Receive user_id
        checkpointer: BaseCheckpointSaver,  # Require checkpointer
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
        self.timeout = self.config.get("timeout", 60)  # Default timeout 60 seconds
        self.system_prompt = self.config.get(
            "system_prompt", "You are a helpful assistant."
        )  # Default prompt

        try:
            # 1. Initialize LLM
            self.llm = self._initialize_llm()

            # 2. Initialize Langchain Tools -> REMOVED (Tools are passed in)
            # self.tools = self._initialize_langchain_tools(
            #     self.tool_definitions,
            #     self.assistant_id,
            # )
            if not self.tools:
                logger.warning(
                    "LangGraphAssistant initialized with no tools.",
                    extra={"assistant_id": self.assistant_id, "user_id": self.user_id},
                )

            # 3. Create the core agent runnable (using self.tools)
            self.agent_runnable = self._create_agent_runnable()

            # 4. Build and compile the custom StateGraph (with checkpointer)
            self.compiled_graph = self._build_graph(checkpointer)

            logger.info(
                "LangGraphAssistant initialized (Custom Graph with Checkpointing)",
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
        log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": state.get("user_id"),  # Get user_id from state
            "current_dialog_state": state.get("dialog_state", ["unknown"])[-1],
        }
        logger.debug("Entering _run_assistant_node", extra=log_extra)

        # Check for triggered event FIRST
        triggered_event = state.get("triggered_event")
        messages_for_agent = list(state["messages"])  # Create a mutable copy
        state_update_from_trigger = {}

        if triggered_event:
            logger.info(
                "Processing triggered event in _run_assistant_node",
                trigger_data=triggered_event,
                extra=log_extra,
            )
            # Craft a message to inform the LLM about the trigger
            trigger_type = triggered_event.get("trigger_type")
            payload = triggered_event.get("payload", {})
            source = triggered_event.get("source", "unknown")
            timestamp = triggered_event.get("timestamp", "unknown")

            trigger_message_content = f"System Notification: Event Triggered\n"
            trigger_message_content += f"Source: {source}\n"
            trigger_message_content += f"Type: {trigger_type}\n"
            trigger_message_content += f"Timestamp (UTC): {timestamp}\n\n"

            # Customize message based on trigger type
            if trigger_type == TriggerType.REMINDER.value:  # Compare with enum value
                trigger_message_content += (
                    f"Reminder ID: {payload.get('reminder_id')}\n"
                    f"Assistant ID: {payload.get('assistant_id')}\n"
                    f"Reminder Type: {payload.get('reminder_type')}\n"
                    f"Reminder Content: {payload.get('payload', {}).get('message', 'No details provided.')}\n\n"
                    f"Please inform the user about this reminder."
                )
            elif (
                trigger_type == TriggerType.GOOGLE_AUTH.value
            ):  # Compare with enum value
                trigger_message_content += (
                    f"Details: Google Calendar authorization was successful.\n\n"
                    f"Please confirm to the user that their Google Calendar is now connected."
                )
            else:
                # Generic message for unknown trigger types
                trigger_message_content += (
                    f"Payload: {str(payload)}\n\n"
                    f"Please acknowledge this system event to the user appropriately."
                )

            # Use HumanMessage to make it clear this is an external event prompt
            trigger_inform_message = HumanMessage(content=trigger_message_content)
            messages_for_agent.append(trigger_inform_message)
            # Mark the trigger as processed by setting it to None in the returned state
            state_update_from_trigger = {"triggered_event": None}
            log_extra["trigger_processed_in_node"] = True

        # Timeout check (optional, could be handled by overall graph timeout)
        # last_activity = state.get("last_activity")
        # if last_activity and (datetime.now(timezone.utc) - last_activity).total_seconds() > self.timeout:
        #     logger.warning(f"Assistant node timeout ({self.timeout}s) exceeded.", extra=log_extra)
        #     return {"messages": [SystemMessage(content="Assistant timed out.")], "dialog_state": "timeout"}

        # Update dialog state
        current_state_update = {
            "dialog_state": "processing",
            "last_activity": datetime.now(timezone.utc),
        }

        agent_outcome = None
        error_message = None

        try:
            # --- Prepare messages for the agent runnable ---
            # We need to include the system prompt if it's not already the first message
            # The process_message method now ensures SystemMessage is first.
            log_extra["message_count_for_agent"] = len(messages_for_agent)

            # Log the messages being sent to the agent runnable
            logger.debug(
                f"Invoking agent runnable with {len(messages_for_agent)} messages",
                extra=log_extra,
            )
            if messages_for_agent:
                logger.debug(
                    f"First message: {str(messages_for_agent[0])[:100]}",
                    extra=log_extra,
                )
                logger.debug(
                    f"Last message: {str(messages_for_agent[-1])[:100]}",
                    extra=log_extra,
                )

            # --- Invoke the agent runnable --- TODO: Add timeout here?
            start_agent_time = time.perf_counter()  # Start agent timer
            # agent_outcome = await self.agent_runnable.ainvoke({"messages": messages_for_agent})
            # Use asyncio.wait_for to apply timeout specifically to the agent runnable call
            agent_outcome = await asyncio.wait_for(
                self.agent_runnable.ainvoke({"messages": messages_for_agent}),
                timeout=self.timeout,
            )
            agent_duration_ms = round((time.perf_counter() - start_agent_time) * 1000)
            log_extra["agent_runnable_duration_ms"] = agent_duration_ms

            logger.debug(
                f"Agent runnable completed in {agent_duration_ms} ms",
                agent_outcome_preview=str(agent_outcome)[:200],
                extra=log_extra,
            )

        except asyncio.TimeoutError:
            logger.error(
                f"Agent runnable timed out after {self.timeout} seconds",
                extra=log_extra,
            )
            error_message = SystemMessage(
                content=f"Processing timed out after {self.timeout} seconds."
            )
            current_state_update["dialog_state"] = "timeout"

        except Exception as e:
            logger.exception(
                "Error invoking agent runnable",
                exc_info=True,
                extra=log_extra,
            )
            # Format a user-friendly error message
            error_content = handle_assistant_error(e, self.name)
            error_message = SystemMessage(content=error_content)
            current_state_update["dialog_state"] = "error"

        # Process outcome or error
        if error_message:
            # If an error occurred, add the error message and update state
            updated_state = {
                **current_state_update,
                "messages": [error_message],
            }
        elif agent_outcome:
            # If successful, update state with agent outcome
            # The agent_outcome is expected to be a dict with a "messages" key
            if isinstance(agent_outcome, dict) and "messages" in agent_outcome:
                updated_state = {
                    **current_state_update,
                    "messages": agent_outcome["messages"],
                    "dialog_state": "pop",  # Go back to idle if successful
                }
            else:
                # Handle unexpected agent outcome format
                logger.error(
                    "Agent runnable returned unexpected outcome format.",
                    outcome=agent_outcome,
                    extra=log_extra,
                )
                error_message = SystemMessage(
                    content="Internal error: Unexpected response format from agent."
                )
                updated_state = {
                    **current_state_update,
                    "messages": [error_message],
                    "dialog_state": "error",
                }
        else:
            # This case should ideally not be reached if try/except handles all
            logger.error(
                "Agent node finished without outcome or error message.", extra=log_extra
            )
            error_message = SystemMessage(
                content="Internal error: Agent processing failed silently."
            )
            updated_state = {
                **current_state_update,
                "messages": [error_message],
                "dialog_state": "error",
            }

        node_duration_ms = round((time.perf_counter() - start_node_time) * 1000)
        log_extra["node_duration_ms"] = node_duration_ms
        logger.debug(
            f"Exiting _run_assistant_node (duration: {node_duration_ms} ms)",
            extra=log_extra,
        )
        return {**updated_state, **state_update_from_trigger}

    def _build_graph(self, checkpointer: BaseCheckpointSaver) -> CompiledGraph:
        """Builds the custom StateGraph, starting directly with the assistant node."""
        builder = StateGraph(AssistantState)

        # --- Add Nodes ---
        # Node that runs the main assistant logic (LLM + ReAct logic)
        builder.add_node("assistant", self._run_assistant_node)
        # Node to execute tools
        builder.add_node("tools", ToolNode(tools=self.tools))

        # --- Add Edges ---
        # Entry point goes directly to the main assistant node
        builder.add_edge(START, "assistant")

        # After the main assistant node runs, check if tools are needed
        builder.add_conditional_edges(
            "assistant",
            tools_condition,  # LangGraph prebuilt condition
            {
                "tools": "tools",  # If tools needed, go to "tools" node
                END: END,  # Otherwise, END
            },
        )

        # After tools are executed, return to the main assistant node
        builder.add_edge("tools", "assistant")

        # Compile the graph with the checkpointer
        logger.info("Compiling graph (START -> assistant)")
        return builder.compile(checkpointer=checkpointer)

    async def process_message(
        self,
        message: Optional[BaseMessage],
        user_id: str,
        triggered_event: Optional[dict] = None,  # Add triggered_event parameter
    ) -> str:
        """Processes a single message using the LangGraph agent and checkpointer."""
        start_time = time.time()  # Start timer
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
        config = {"configurable": {"thread_id": user_id}}

        # Prepare initial state update
        initial_state_update = {
            "user_id": user_id,
            "dialog_state": ["processing"],
            "last_activity": datetime.now(timezone.utc),
            "triggered_event": triggered_event,  # Pass the trigger event
            # Always include the system prompt (as SystemMessage) if it exists,
            # followed by the current message
            "messages": (
                [SystemMessage(content=self.system_prompt)]
                if self.system_prompt
                else []
            )
            + ([message] if message else []),
        }

        try:
            logger.debug(
                f"Invoking compiled_graph.ainvoke for user {user_id}", extra=log_extra
            )
            # Use ainvoke for asynchronous execution
            # Apply timeout to the graph invocation
            final_state = await asyncio.wait_for(
                self.compiled_graph.ainvoke(initial_state_update, config=config),
                timeout=self.timeout,
            )
            logger.debug(
                f"Graph invocation completed for user {user_id}", extra=log_extra
            )

            # Extract the last AI message from the final state
            if final_state and "messages" in final_state and final_state["messages"]:
                last_message = final_state["messages"][-1]
                if isinstance(last_message, AIMessage):
                    response_content = last_message.content
                    end_time = time.time()  # End timer
                    log_extra["duration_ms"] = round((end_time - start_time) * 1000)
                    logger.info(
                        f"Successfully processed message for user {user_id}",
                        response_preview=f"{str(response_content)[:100]}...",
                        extra=log_extra,
                    )
                    return response_content
                else:
                    logger.warning(
                        f"Last message in final state is not an AIMessage (Type: {type(last_message).__name__})",
                        extra=log_extra,
                    )
                    # Fallback or error handling? Return empty for now.
                    return ""
            else:
                logger.warning(
                    "No messages found in final state",
                    final_state=final_state,
                    extra=log_extra,
                )
                return ""  # Or raise an error?

        except asyncio.TimeoutError:
            logger.error(
                f"Timeout occurred processing message for user {user_id}",
                extra=log_extra,
            )
            # Optionally, update dialog state to 'timeout'
            # await self.compiled_graph.update_state(config, {"dialog_state": "timeout"})
            raise MessageProcessingError(
                f"Processing timed out after {self.timeout} seconds.", self.name
            )
        except Exception as e:
            logger.exception(
                f"Error processing message for user {user_id}: {e}",
                extra=log_extra,
                exc_info=True,
            )
            # Optionally, update dialog state to 'error'
            # await self.compiled_graph.update_state(config, {"dialog_state": "error"})
            # Use the centralized error handler
            return handle_assistant_error(e, assistant_name=self.name)

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
