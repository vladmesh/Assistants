# assistant_service/src/assistants/langgraph/graph_builder.py

import functools
import logging
from typing import List, Literal

# Import the new node
from assistants.langgraph.nodes.ensure_context_limit import ensure_context_limit_node
from assistants.langgraph.nodes.summarize_history import (  # Keep summarize imports
    should_summarize,
    summarize_history_node,
)

# Project specific imports
from assistants.langgraph.state import AssistantState
from langchain_core.language_models.chat_models import BaseChatModel  # For summary_llm

# Langchain core and specific components
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode, tools_condition

logger = logging.getLogger(__name__)


def route_after_assistant(state: AssistantState) -> Literal["tools", END]:
    """Determines the next step after the main assistant node runs.
    If tools are called, go to 'tools'. Otherwise, END.
    Summary check is now handled after tools.
    """
    log_extra = state.get("log_extra", {})
    messages = state.get("messages", [])
    msg_types = [type(m).__name__ for m in messages]
    logger.info(
        f"[route_after_assistant] ENTERED. Msgs: {len(messages)}, Types: {msg_types}"
    )
    logger.debug("Routing after assistant node.", extra=log_extra)
    if tools_condition(state) == "tools":
        logger.debug("Routing -> tools", extra=log_extra)
        return "tools"

    logger.debug("Routing -> END", extra=log_extra)
    return END

    # --- End New Condition Function ---


def build_full_graph(
    run_node_fn,  # The main agent execution function (LangGraphAssistant._run_assistant_node)
    tools: List[BaseTool],
    checkpointer: BaseCheckpointSaver,
    summary_llm: BaseChatModel,  # Keep for summary node
) -> CompiledGraph:
    """Builds the complete LangGraph state machine (v2.3 - with ensure_context_limit).

    Includes:
    - Conditional history summarization (checked at START and after TOOLS)
    - GUARANTEED context limit enforcement via ensure_context_limit node.
    - Main agent loop (LLM call + Tool execution)
    """
    builder = StateGraph(AssistantState)

    # --- Nodes --- #
    logger.debug("Defining graph nodes...")

    # 1. summarize: Optional node to summarize history
    bound_summarize_node = functools.partial(
        summarize_history_node, summary_llm=summary_llm
    )
    builder.add_node("summarize", bound_summarize_node)
    logger.debug("Added node: summarize")

    # 2. ensure_limit: Node to enforce token limits via truncation if needed
    builder.add_node("ensure_limit", ensure_context_limit_node)
    logger.debug("Added node: ensure_limit")

    # 3. assistant: The core node running the agent logic (LLM call)
    builder.add_node("assistant", run_node_fn)
    logger.debug("Added node: assistant")

    # 4. tools: Node that executes tools chosen by the assistant
    builder.add_node("tools", ToolNode(tools=tools))
    logger.debug("Added node: tools")

    # --- Edges --- #
    logger.debug("Defining graph edges...")
    builder.add_conditional_edges(
        START,
        should_summarize,  # Check summary need immediately
        {
            "summarize": "summarize",
            "assistant": "ensure_limit",  # If no summary needed, still check limit before assistant
        },
    )
    logger.debug(
        "Added conditional edge: START -> should_summarize (targets: summarize, ensure_limit)"
    )

    # summarize -> ensure_limit (Always check limit after attempting summary)
    builder.add_edge("summarize", "ensure_limit")
    logger.debug("Added edge: summarize -> ensure_limit")

    # ensure_limit -> assistant (Always go to assistant after ensuring limit)
    builder.add_edge("ensure_limit", "assistant")
    logger.debug("Added edge: ensure_limit -> assistant")

    # assistant -> tools or END
    builder.add_conditional_edges(
        "assistant",
        route_after_assistant,
        {"tools": "tools", END: END},
    )
    logger.debug(
        "Added conditional edge: assistant -> route_after_assistant (targets: tools, END)"
    )

    # tools -> summarize or ensure_limit
    builder.add_conditional_edges(
        "tools",
        should_summarize,  # Check summary need after tools run
        {
            "summarize": "summarize",
            "assistant": "ensure_limit",  # If no summary needed, still check limit before assistant
        },
    )
    logger.debug(
        "Added conditional edge: tools -> should_summarize (targets: summarize, ensure_limit)"
    )

    # --- Compile Graph --- #
    logger.info("Compiling LangGraph with ensure_context_limit node (v2.3).")
    return builder.compile(checkpointer=checkpointer)
