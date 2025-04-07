# assistant_service/src/assistants/langgraph_assistant.py

import logging
from datetime import datetime, timezone  # Import timezone
from typing import Annotated, Any, Dict, List, Literal, Optional

# Project specific imports
from assistants.base_assistant import BaseAssistant

# --- Tool Imports ---
# Import specific tool implementation classes directly for now
# TODO: Refactor using a ToolFactory later
from config.settings import settings  # To get API keys if not in assistant config

# Base classes and core types
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI

# LangGraph components
from langgraph.checkpoint.base import (  # Import needed for checkpointer
    BaseCheckpointSaver,
)
from langgraph.graph import START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.graph.state import CompiledGraph
from langgraph.prebuilt import create_react_agent  # Import create_react_agent
from langgraph.prebuilt import ToolNode, tools_condition
from tools.calendar_tool import CalendarCreateTool, CalendarListTool
from tools.reminder_tool import ReminderTool
from tools.time_tool import TimeToolWrapper
from tools.web_search_tool import WebSearchTool
from typing_extensions import TypedDict

# --- End Tool Imports ---
from utils.error_handler import handle_assistant_error  # Import error handlers
from utils.error_handler import AssistantError, MessageProcessingError

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

    def _build_graph(self, checkpointer: BaseCheckpointSaver) -> CompiledGraph:
        """Builds the custom StateGraph."""
        builder = StateGraph(AssistantState)

        # Add nodes
        builder.add_node("assistant", self._run_assistant_node)
        builder.add_node("tools", ToolNode(tools=self.tools))

        # Add edges
        builder.add_edge(START, "assistant")  # Start with the assistant node
        builder.add_edge("tools", "assistant")  # After tools, return to assistant

        # Add conditional edges
        builder.add_conditional_edges(
            "assistant",  # Node where decision is made
            tools_condition,  # Function to check if tools should be called
            # Mapping: "tools" -> call tools, END -> finish
        )
        # The tools_condition function routes to "__end__" or the tools node name

        # Compile the graph with the checkpointer
        return builder.compile(checkpointer=checkpointer)

    async def _run_assistant_node(self, state: AssistantState) -> dict:
        """The node that runs the core agent logic, including timeout and state updates."""
        log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": state.get("user_id"),
            "thread_id": state.get(
                "thread_id"
            ),  # Assuming thread_id is part of state if checkpointing
            "current_dialog_state": state.get("dialog_state", ["unknown"])[-1]
            if state.get("dialog_state")
            else "unknown",
        }
        logger.debug("Running assistant node", extra=log_extra)

        try:
            # 1. Update last activity time
            now = datetime.now(timezone.utc)  # Use timezone-aware datetime
            last_activity_update = {"last_activity": now}

            # 2. Check for timeout (only if last_activity is present)
            last_activity = state.get("last_activity")
            if last_activity and (now - last_activity).seconds > self.timeout:
                logger.warning("Assistant timeout detected", extra=log_extra)
                return {
                    **last_activity_update,
                    "dialog_state": "timeout",
                    "messages": [
                        SystemMessage(content="Conversation timed out.")
                    ],  # Use add_messages by returning list
                }

            # 3. Update dialog state to processing
            dialog_state_update = {"dialog_state": "processing"}

            # 4. Prepare messages for the agent runnable
            # Ensure System Prompt is included if not implicitly handled by create_react_agent
            current_messages = state["messages"]
            messages_for_agent = current_messages
            # Check if system message is already the first message
            if not current_messages or not isinstance(
                current_messages[0], SystemMessage
            ):
                messages_for_agent = [
                    SystemMessage(content=self.system_prompt)
                ] + current_messages
                logger.debug("Prepended system prompt", extra=log_extra)

            # 5. Invoke the core agent runnable
            logger.debug("Invoking agent runnable", extra=log_extra)
            agent_input = {"messages": messages_for_agent}
            # How to pass user_id? Option 1: Include in state (done). Option 2: Config?
            # create_react_agent doesn't directly support passing arbitrary args like user_id via invoke.
            # Tools need to be aware of how to get context if needed (e.g., from state via a wrapper, or passed during init if static).
            # For now, rely on tools accessing context through other means if necessary.
            response = await self.agent_runnable.ainvoke(agent_input)
            logger.debug(
                "Agent runnable response received",
                extra={**log_extra, "response": response},
            )

            # 6. Process response and prepare state update
            # create_react_agent returns state dict, last message is in response['messages'][-1]
            if not response or "messages" not in response or not response["messages"]:
                raise MessageProcessingError(
                    "Agent runnable returned empty or invalid response", self.name
                )

            last_message = response["messages"][-1]

            # Ensure the response is added correctly for add_messages
            response_update = {"messages": [last_message]}

            # 7. Update dialog state back to idle
            # Use "pop" to remove "processing", then add "idle"
            # LangGraph manages the state stack based on the updater function (update_dialog_stack)
            # Returning 'idle' should push 'idle' onto the stack
            final_dialog_state_update = {"dialog_state": "idle"}

            # Combine updates: activity time, response message, final dialog state
            # The state merger should handle combining these dicts.
            return {
                **last_activity_update,
                **response_update,
                **final_dialog_state_update,
            }

        except Exception as e:
            logger.exception("Error in assistant node", extra=log_extra, exc_info=True)
            error_msg = handle_assistant_error(e, self.name)
            # Return state updates indicating error
            return {
                "last_activity": datetime.now(
                    timezone.utc
                ),  # Update time even on error
                "dialog_state": "error",
                "messages": [SystemMessage(content=error_msg)],  # Add error message
            }

    async def process_message(self, message: BaseMessage, user_id: str) -> str:
        """
        Processes an incoming message using the compiled LangGraph with checkpointing.
        The thread_id for persistence is generated internally based on user_id.

        Args:
            message: The input message (standard Langchain BaseMessage).
            user_id: The identifier of the user initiating the request.

        Returns:
            A string containing the assistant's response.
        """
        # Generate thread_id based on user_id
        thread_id = f"user_{user_id}"
        invoke_config = {"configurable": {"thread_id": str(thread_id)}}  # Ensure string

        log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": user_id,
            "thread_id": thread_id,  # Log the generated thread_id
            "message_type": type(message).__name__,
        }
        logger.debug("Processing message via compiled graph", extra=log_extra)

        try:
            # Ensure user_id is passed in the initial graph state if needed by nodes/tools
            # Our current AssistantState includes user_id, so this should be okay.
            graph_input: Dict[str, Any] = {"messages": [message], "user_id": user_id}

            # Invoke the graph
            final_state_dict = await self.compiled_graph.ainvoke(
                graph_input,
                config=invoke_config,
            )

            # Cast to AssistantState type for safety, though it's a dict
            # final_state = AssistantState(**final_state_dict) # This might fail if state keys missing
            final_state = final_state_dict

            # Extract the last response message
            if final_state and final_state.get("messages"):
                last_message = final_state["messages"][-1]
                # Check if the last message is from the AI
                if isinstance(last_message, AIMessage):
                    response_content = str(last_message.content)
                    logger.info(
                        "Message processed successfully (via graph)",
                        extra={**log_extra, "response_length": len(response_content)},
                    )
                    return response_content
                # Handle cases where the last message might be a system error message
                elif (
                    isinstance(last_message, SystemMessage)
                    and final_state.get("dialog_state")
                    and final_state.get("dialog_state")[-1] == "error"
                ):
                    logger.error(
                        "Graph processing finished with an error state.",
                        extra=log_extra,
                    )
                    return f"Assistant Error: {last_message.content}"
                else:
                    logger.warning(
                        "Last message in graph state is not an AIMessage",
                        extra={
                            **log_extra,
                            "last_message_type": type(last_message).__name__,
                        },
                    )
                    return "Assistant processed the request but the final output wasn't standard text."
            else:
                logger.error(
                    "Graph execution finished but no messages found in final state.",
                    extra={**log_extra, "final_state": final_state},
                )
                return "Error: Assistant finished processing but produced no response."

        except Exception:
            logger.exception(
                "Error during graph invocation", extra=log_extra, exc_info=True
            )
            return f"Sorry, a critical error occurred while processing your request in assistant '{self.name}'."

    # Optional: Add a close method if needed (e.g., for resource cleanup)
    # async def close(self):
    #     logger.info(f"Closing assistant {self.name}")
    # Add cleanup logic here if necessary
