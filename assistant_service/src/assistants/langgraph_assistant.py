# assistant_service/src/assistants/langgraph_assistant.py

import logging
from typing import Any, Dict, List, Optional

# Base classes and core types
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledGraph  # For type hinting

# LangGraph components
# from langgraph.checkpoint import BaseCheckpointSaver # Not used yet
from langgraph.prebuilt import create_react_agent

# --- End Tool Imports ---
from ..config import settings  # To get API keys if not in assistant config
from ..tools.calendar_tool import CalendarCreateTool, CalendarListTool
from ..tools.reminder_tool import ReminderTool

# --- Tool Imports ---
# Import specific tool implementation classes directly for now
# TODO: Refactor using a ToolFactory later
from ..tools.time_tool import TimeToolWrapper
from ..tools.web_search_tool import WebSearchTool
from ..utils.error_handler import AssistantError

# Project specific imports
from .base_assistant import BaseAssistant

logger = logging.getLogger(__name__)


class LangGraphAssistant(BaseAssistant):
    """
    Assistant implementation using LangGraph.
    Leverages a React agent created via LangGraph prebuilt functions.
    Handles optional thread_id for stateless/stateful invocation context.
    Does NOT use persistent checkpointing yet.
    """

    compiled_graph: CompiledGraph  # Add type hint for the compiled graph

    def __init__(
        self,
        assistant_id: str,
        name: str,
        config: Dict,
        tool_definitions: List[Dict],
        **kwargs,
    ):
        """
        Initializes the LangGraphAssistant.

        Args:
            assistant_id: Unique identifier for the assistant instance.
            name: Name of the assistant.
            config: Dictionary containing all configuration parameters.
                    Expected keys: 'model_name', 'temperature', 'api_key' (optional),
                                   'system_prompt', etc.
            tool_definitions: List of raw tool definitions from the database.
            **kwargs: Additional keyword arguments.
        """
        super().__init__(assistant_id, name, config, tool_definitions, **kwargs)

        try:
            # 1. Initialize LLM
            self.llm = self._initialize_llm()

            # 2. Initialize Langchain Tools (excluding sub-assistants for now)
            self.tools = self._initialize_langchain_tools(
                self.tool_definitions,
                self.assistant_id,  # Pass assistant_id in case tools need it (like ReminderTool)
            )

            # 3. Create and compile the LangGraph agent (React agent for now)
            # No checkpointer is passed, making it non-persistent across restarts,
            # but stateful within a single invocation if thread_id is provided.
            self.compiled_graph = create_react_agent(self.llm, self.tools)

            logger.info(
                "LangGraphAssistant initialized (stateless persistence)",
                extra={
                    "assistant_id": self.assistant_id,
                    "name": self.name,
                    "tools_count": len(self.tools),
                },
            )

        except Exception as e:
            logger.exception(
                "Failed to initialize LangGraphAssistant",
                extra={"assistant_id": self.assistant_id, "name": self.name},
                exc_info=True,
            )
            raise AssistantError(
                f"Failed to initialize LangGraph assistant '{name}': {e}"
            ) from e

    def _initialize_llm(self) -> ChatOpenAI:
        """Initializes the language model based on configuration."""
        model_name = self.config.get("model_name", "gpt-4o-mini")  # Default model
        temperature = self.config.get("temperature", 0.7)
        api_key = self.config.get("api_key", settings.openai_api_key)

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
        # TODO: Add handling for other LLM providers if needed based on config
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            # streaming=True, # Consider adding if streaming is needed
        )

    def _initialize_langchain_tools(
        self, tool_definitions: List[Dict], assistant_id_for_tools: str
    ) -> List[Tool]:
        """
        Initializes Langchain Tool instances from raw definitions.
        Currently skips 'sub_assistant' type.
        TODO: Refactor this logic into a dedicated ToolFactory.
        """
        initialized_tools = []
        for tool_def in tool_definitions:
            tool_type = tool_def.get("tool_type")
            tool_name = tool_def.get("name")
            tool_description = tool_def.get("description")
            input_schema_str = tool_def.get(
                "input_schema"
            )  # Assuming schema is stored as JSON string

            tool_instance: Optional[Tool] = None
            log_extra = {
                "assistant_id": self.assistant_id,
                "tool_name": tool_name,
                "tool_type": tool_type,
            }

            try:
                if tool_type == "time":
                    tool_instance = (
                        TimeToolWrapper()
                    )  # Assumes TimeToolWrapper creates a valid Langchain Tool
                elif tool_type == "web_search":
                    # Pass Tavily key from global settings or potentially from config
                    tavily_api_key = settings.tavily_api_key
                    if tavily_api_key:
                        tool_instance = WebSearchTool(tavily_api_key=tavily_api_key)
                    else:
                        logger.warning(
                            "TAVILY_API_KEY not set, skipping WebSearchTool.",
                            extra=log_extra,
                        )
                elif tool_type == "calendar":
                    # Differentiate based on name for calendar tools
                    if tool_name == "calendar_create":
                        tool_instance = CalendarCreateTool()
                    elif tool_name == "calendar_list":
                        tool_instance = CalendarListTool()
                    else:
                        logger.warning(
                            f"Unknown calendar tool name: {tool_name}", extra=log_extra
                        )
                elif tool_type == "reminder":
                    # ReminderTool might need assistant_id or user_id context later
                    # Pass assistant_id for now, user_id is handled in process_message context if needed by the tool internally
                    tool_instance = ReminderTool(assistant_id=assistant_id_for_tools)
                elif tool_type == "sub_assistant":
                    logger.warning(
                        "Skipping sub_assistant tool initialization for now.",
                        extra=log_extra,
                    )
                else:
                    logger.warning(
                        f"Unknown tool type '{tool_type}'. Cannot initialize.",
                        extra=log_extra,
                    )

                if tool_instance:
                    initialized_tools.append(tool_instance)
                    logger.info("Initialized tool", extra=log_extra)

            except Exception as e:
                logger.error(
                    "Failed to initialize tool", extra=log_extra, exc_info=True
                )
                # Decide whether to skip or raise: raise AssistantError(f"Failed to init tool {tool_name}: {e}") from e

        return initialized_tools

    async def process_message(
        self, message: BaseMessage, user_id: str, thread_id: Optional[str] = None
    ) -> str:
        """
        Processes an incoming message using the LangGraph agent.
        Handles thread_id context for stateless/stateful invocation.

        Args:
            message: The input message (standard Langchain BaseMessage).
            user_id: The identifier of the user initiating the request.
            thread_id: Optional identifier for the conversation thread.

        Returns:
            A string containing the assistant's response.
        """
        log_extra = {
            "assistant_id": self.assistant_id,
            "user_id": user_id,
            "thread_id": thread_id,
            "message_type": type(message).__name__,
        }
        logger.debug("Processing message with LangGraphAssistant", extra=log_extra)

        # Prepare input for the graph
        graph_input = {"messages": [message]}

        # Config for invocation - LangGraph uses thread_id if provided
        invoke_config = {"configurable": {"thread_id": thread_id}}

        try:
            # Invoke the graph. Use ainvoke for standard request/response.
            # Use astream or astream_events for streaming responses later.
            final_state = await self.compiled_graph.ainvoke(
                graph_input, config=invoke_config
            )

            # Extract the last response (usually an AIMessage)
            if final_state and "messages" in final_state and final_state["messages"]:
                last_message = final_state["messages"][-1]
                if isinstance(last_message, AIMessage):
                    response_content = str(
                        last_message.content
                    )  # Ensure string conversion
                    logger.info(
                        "LangGraphAssistant processed message successfully",
                        extra={**log_extra, "response_length": len(response_content)},
                    )
                    return response_content
                else:
                    logger.warning(
                        "Last message in graph state is not an AIMessage",
                        extra={
                            **log_extra,
                            "last_message_type": type(last_message).__name__,
                        },
                    )
                    # Fallback response if the structure is unexpected
                    return "Assistant processed the request but the final output wasn't standard text."
            else:
                logger.error(
                    "Graph execution finished but no messages found in final state.",
                    extra={**log_extra, "final_state": final_state},
                )
                return "Error: Assistant finished processing but produced no response."

        except Exception as e:
            logger.exception(
                "Error processing message with LangGraphAssistant",
                extra=log_extra,
                exc_info=True,
            )
            # Return a user-friendly error message
            return f"Sorry, an error occurred while processing your request in assistant '{self.name}'."
