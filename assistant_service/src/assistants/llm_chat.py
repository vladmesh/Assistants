"""Base LLM chat assistant implementation"""

from abc import ABC
from datetime import datetime
from typing import Annotated, Any, List, Literal, Optional

from assistants.base import BaseAssistant
from config.logger import get_logger
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage
from langgraph.graph import START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, create_react_agent, tools_condition
from messages.base import BaseMessage, HumanMessage, SystemMessage
from tools.base import BaseTool
from typing_extensions import TypedDict
from utils.error_handler import (
    AssistantError,
    MessageProcessingError,
    handle_assistant_error,
)

logger = get_logger(__name__)


def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]


class AssistantState(TypedDict):
    """State for the assistant"""

    messages: Annotated[list[AnyMessage], add_messages]
    user_id: Optional[str]
    dialog_state: Annotated[
        list[Literal["idle", "processing", "waiting_for_tool", "error", "timeout"]],
        update_dialog_stack,
    ]
    last_activity: datetime


class BaseLLMChat(BaseAssistant, ABC):
    """Base class for LLM chat assistants"""

    def __init__(
        self,
        llm: BaseLanguageModel,
        system_message: Optional[str] = None,
        tools: Optional[List[BaseTool]] = None,
        name: str = "base_llm_chat",
        instructions: str = "You are a helpful assistant",
        timeout: int = 30,
        is_secretary: bool = False,
        assistant_id: Optional[str] = None,
    ):
        try:
            super().__init__(name=name, instructions=instructions, tools=tools)
            self.llm = llm
            self.system_message = system_message or instructions
            self.timeout = timeout
            self.is_secretary = is_secretary
            self.assistant_id = assistant_id
            self.agent = self._create_agent()
            self.graph = self._create_graph()
        except Exception as e:
            raise AssistantError(f"Failed to initialize assistant: {str(e)}", name)

    def _create_agent(self) -> Any:
        """Create the agent using LangGraph

        Raises:
            AssistantError: If agent creation fails
        """
        try:
            return create_react_agent(
                self.llm,
                self.tools,
                prompt=self.system_message if self.system_message else None,
            )
        except Exception as e:
            raise AssistantError(f"Failed to create agent: {str(e)}", self.name)

    def _create_graph(self) -> StateGraph:
        """Create the LangGraph workflow

        Returns:
            StateGraph: Configured graph for message processing
        """
        builder = StateGraph(AssistantState)

        # Add nodes
        builder.add_node(self.name, self._process_message)
        builder.add_node("tools", ToolNode(tools=self.tools))

        # Add edges
        builder.add_edge(START, self.name)  # Entry point
        builder.add_edge("tools", self.name)  # Return from tools

        # Add conditional edges
        builder.add_conditional_edges(
            self.name,
            tools_condition,
        )

        return builder.compile()

    async def _process_message(self, state: AssistantState) -> dict:
        """Process a message using the agent

        Args:
            state: Current state of the assistant

        Returns:
            dict: Updated state
        """
        try:
            # Update last activity
            state["last_activity"] = datetime.now()

            # Check timeout
            if (datetime.now() - state["last_activity"]).seconds > self.timeout:
                state["dialog_state"].append("timeout")
                return state

            # Process message
            state["dialog_state"].append("processing")

            # Convert messages to the format expected by LangGraph
            messages = []
            for msg in state["messages"]:
                if isinstance(msg, HumanMessage):
                    messages.append({"role": "human", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages.append({"role": "assistant", "content": msg.content})
                elif isinstance(msg, SystemMessage):
                    messages.append({"role": "system", "content": msg.content})
                else:
                    messages.append({"role": "user", "content": str(msg)})

            logger.debug(
                "Invoking agent with messages",
                messages=messages,
                user_id=state["user_id"],
                assistant_name=self.name,
            )

            # Add user_id to the input for tools
            try:
                response = await self.agent.ainvoke(
                    {"messages": messages, "user_id": state["user_id"]}
                )
                logger.debug(
                    "Agent response received",
                    response=response,
                    response_type=type(response).__name__,
                    assistant_name=self.name,
                )
            except Exception as e:
                logger.error(
                    "Agent invocation failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    error_traceback=e.__traceback__,
                    assistant_name=self.name,
                    exc_info=True,
                )
                raise

            if not response:
                raise MessageProcessingError("Agent returned empty response", self.name)

            # Convert response to the format expected by LangGraph
            if isinstance(response, AIMessage):
                response = {"role": "assistant", "content": response.content}
            elif isinstance(response, dict) and "messages" in response:
                # If response contains multiple messages, take the last one
                last_message = response["messages"][-1]
                if isinstance(last_message, AIMessage):
                    response = {"role": "assistant", "content": last_message.content}
                else:
                    response = {"role": "assistant", "content": str(last_message)}
            else:
                response = {"role": "assistant", "content": str(response)}

            logger.debug(
                "Converted response",
                response=response,
                assistant_name=self.name,
            )

            # Update state
            state["messages"].append(response)
            state["dialog_state"].pop()  # Remove "processing"
            state["dialog_state"].append("idle")

            return state

        except Exception as e:
            logger.error(
                "Error in _process_message",
                error=str(e),
                error_type=type(e).__name__,
                error_traceback=e.__traceback__,
                state=state,
                assistant_name=self.name,
                exc_info=True,
            )
            error_msg = handle_assistant_error(e, self.name)
            state["dialog_state"].append("error")
            state["messages"].append({"role": "system", "content": error_msg})
            return state

    async def process_message(
        self, message: BaseMessage, user_id: Optional[str] = None
    ) -> str:
        """Process a message using the graph

        Args:
            message: Input message to process
            user_id: Optional user identifier

        Returns:
            Assistant's response

        Raises:
            MessageProcessingError: If message processing fails
        """
        try:
            logger.debug(
                "Starting message processing",
                message_type=type(message).__name__,
                message_content=message.content,
                user_id=user_id,
                assistant_name=self.name,
            )

            # Set tool context with user_id
            self._set_tool_context(user_id)
            logger.debug("Tool context set", user_id=user_id)

            # Initialize state
            state = {
                "messages": [message],
                "user_id": user_id,
                "dialog_state": ["idle"],
                "last_activity": datetime.now(),
            }
            logger.debug("State initialized", state=state)

            # Process through graph
            logger.debug("Starting graph processing")
            result = await self.graph.ainvoke(state)
            logger.debug("Graph processing completed", result=result)

            # Get last message
            if not result["messages"]:
                logger.error("No messages in result")
                return "Извините, произошла ошибка при обработке сообщения"

            last_message = result["messages"][-1]
            logger.debug("Processing last message", last_message=last_message)

            if isinstance(last_message, AIMessage):
                return last_message.content
            elif isinstance(last_message, dict):
                return last_message.get(
                    "content", "Извините, произошла ошибка при обработке сообщения"
                )
            elif isinstance(last_message, str):
                # Try to parse as dict
                try:
                    msg_dict = eval(last_message)
                    if isinstance(msg_dict, dict):
                        return msg_dict.get(
                            "content",
                            "Извините, произошла ошибка при обработке сообщения",
                        )
                except:
                    pass
            return str(last_message)

        except Exception as e:
            logger.error(
                "Unexpected error in process_message",
                error=str(e),
                error_type=type(e).__name__,
                assistant_name=self.name,
                exc_info=True,
            )
            return "Извините, произошла непредвиденная ошибка"

    async def close(self):
        """Close assistant and cleanup resources"""
        try:
            logger.info("Assistant closed successfully")
        except Exception as e:
            logger.error("Error while closing assistant", error=str(e), exc_info=True)
