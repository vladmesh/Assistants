# assistant_service/src/assistants/langgraph/graph_builder.py

import functools
import logging
from typing import List, Literal

# Import the new node
from assistants.langgraph.nodes.ensure_context_limit import ensure_context_limit_node
from assistants.langgraph.nodes.run_assistant import run_assistant_node
from assistants.langgraph.nodes.summarize_history import (  # Keep summarize imports
    should_summarize,
    summarize_history_node,
)

# Import state and cache types
from assistants.langgraph.prompt_context_cache import PromptContextCache  # NEW

# Project specific imports
from assistants.langgraph.state import AssistantState
from langchain_core.language_models.chat_models import BaseChatModel  # For summary_llm
from langchain_core.runnables import Runnable

# Langchain core and specific components
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode, tools_condition
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)


def route_after_assistant(state: AssistantState) -> Literal["tools", END]:
    """Determines the next step after the main assistant node runs.
    If tools are called, go to 'tools'. Otherwise, END.
    Summary check is now handled before assistant node.
    """
    state.get("log_extra", {})
    messages = state.get("messages", [])
    msg_types = [type(m).__name__ for m in messages]
    logger.info(
        f"[route_after_assistant] ENTERED. Msgs: {len(messages)}, Types: {msg_types}"
    )
    if tools_condition(state) == "tools":
        return "tools"

    return END


def build_full_graph(
    tools: List[BaseTool],
    checkpointer: BaseCheckpointSaver,
    summary_llm: BaseChatModel,  # Keep for summary node
    rest_client: RestServiceClient,  # Still needed for summarize_history_node (saving)
    prompt_context_cache: PromptContextCache,  # NEW: Pass shared cache
    system_prompt_template: str,
    agent_runnable: Runnable,
    timeout: int = 30,
) -> CompiledGraph:
    """Builds the complete LangGraph state machine (v2.5 - shared cache for token checks).

    Includes:
    - Conditional history summarization (saves via REST)
    - GUARANTEED context limit enforcement (uses shared cache for token check)
    - Main agent loop (LLM call + Tool execution)
    """
    builder = StateGraph(AssistantState)

    # --- Nodes --- #

    # 1. summarize: Node to summarize history and save via REST
    # Still needs summary_llm and rest_client
    bound_summarize_node = functools.partial(
        summarize_history_node, summary_llm=summary_llm, rest_client=rest_client
    )
    builder.add_node("summarize", bound_summarize_node)

    # 2. ensure_limit: Node to enforce token limits via truncation if needed
    # NEW: Pass cache and template for accurate token calculation
    bound_ensure_limit_node = functools.partial(
        ensure_context_limit_node,
        prompt_context_cache=prompt_context_cache,
        system_prompt_template=system_prompt_template,
    )
    builder.add_node("ensure_limit", bound_ensure_limit_node)

    # 3. run_assistant: The core node running the agent logic (LLM call)
    bound_run_assistant_node = functools.partial(
        run_assistant_node, agent_runnable=agent_runnable, timeout=timeout
    )
    builder.add_node("assistant", bound_run_assistant_node)

    # 4. tools: Node that executes tools chosen by the assistant
    builder.add_node("tools", ToolNode(tools=tools))

    # --- Edges --- #

    # --- Conditional Edge Function (should_summarize) --- #
    # NEW: Bind cache and template to should_summarize for accurate check
    bound_should_summarize_condition = functools.partial(
        should_summarize,
        prompt_context_cache=prompt_context_cache,
        system_prompt_template=system_prompt_template
        # Note: rest_client is NOT needed here if cache is used for check
    )
    # --------------------------------------------------- #

    builder.add_conditional_edges(
        START,
        bound_should_summarize_condition,  # Use bound condition function
        {
            "summarize": "summarize",
            "assistant": "ensure_limit",
        },
    )

    builder.add_edge("summarize", "ensure_limit")

    builder.add_edge("ensure_limit", "assistant")

    builder.add_conditional_edges(
        "assistant",
        route_after_assistant,
        {"tools": "tools", END: END},
    )

    builder.add_conditional_edges(
        "tools",
        bound_should_summarize_condition,  # Use bound condition function again
        {
            "summarize": "summarize",
            "assistant": "ensure_limit",
        },
    )

    # --- Compile Graph --- #
    return builder.compile(checkpointer=checkpointer)
