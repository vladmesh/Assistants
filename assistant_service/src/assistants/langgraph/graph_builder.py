# assistant_service/src/assistants/langgraph/graph_builder.py

import functools
import logging
from typing import Any, Callable, List

from assistants.langgraph.nodes.entry_check_facts import entry_check_facts_node
from assistants.langgraph.nodes.init_state import init_state_node
from assistants.langgraph.nodes.load_user_facts import load_user_facts_node
from assistants.langgraph.nodes.update_state_after_tool import (
    update_state_after_tool_node,
)
from assistants.langgraph.state import AssistantState
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledGraph
from langgraph.prebuilt import ToolNode, tools_condition
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)


def build_full_graph(
    run_node_fn: Callable[[AssistantState], dict],
    tools: List[BaseTool],
    checkpointer: BaseCheckpointSaver,
    rest_client: RestServiceClient,
    system_prompt_text: str,
) -> CompiledGraph:
    """
    Builds the full agent graph structure including initialization, fact handling, and agent logic.

    Args:
        run_node_fn: The asynchronous function representing the main agent logic node.
        tools: A list of initialized Langchain tools for the agent.
        checkpointer: The checkpoint saver instance for persisting state.
        rest_client: The REST client instance needed for the fact check node.
        system_prompt_text: The text content for the main system prompt.

    Returns:
        The compiled LangGraph.
    """
    logger.debug("Building full graph with init_state, fact checking and loading")
    graph_builder = StateGraph(AssistantState)

    # 1. Add init_state node
    bound_init_node = functools.partial(
        init_state_node, system_prompt_text=system_prompt_text
    )
    graph_builder.add_node("init_state", bound_init_node)

    # 2. Add entry node: check_facts
    bound_entry_node = functools.partial(
        entry_check_facts_node, rest_client=rest_client
    )
    graph_builder.add_node("check_facts", bound_entry_node)

    # 3. Add node: load_facts
    graph_builder.add_node("load_facts", load_user_facts_node)

    # 4. Add node: assistant
    graph_builder.add_node("assistant", run_node_fn)

    # 5. Add node: tools
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)

    # 6. Define Edges
    graph_builder.add_edge(START, "init_state")  # Entry point to init_state
    graph_builder.add_edge("init_state", "check_facts")  # After init, check facts
    graph_builder.add_edge("check_facts", "load_facts")  # After checking, load facts
    graph_builder.add_edge(
        "load_facts", "assistant"
    )  # After loading facts, go to assistant

    # Conditional edges from assistant (tool calling)
    graph_builder.add_conditional_edges(
        "assistant",
        tools_condition,
        {
            "tools": "tools",
            END: END,
        },
    )
    # Edge back from tools to assistant
    graph_builder.add_node("update_state_after_tool", update_state_after_tool_node)
    graph_builder.add_edge("tools", "update_state_after_tool")
    graph_builder.add_edge("update_state_after_tool", "assistant")

    # 7. Compile graph
    graph = graph_builder.compile(checkpointer=checkpointer)
    logger.debug("Full graph compiled with init_state")
    return graph
