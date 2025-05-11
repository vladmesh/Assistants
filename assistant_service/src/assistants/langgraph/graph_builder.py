# assistant_service/src/assistants/langgraph/graph_builder.py

import functools
import logging
from typing import List, Literal

# Import existing nodes
from assistants.langgraph.nodes.finalize_processing import finalize_processing_node

# Import new nodes
from assistants.langgraph.nodes.load_context import load_context_node
from assistants.langgraph.nodes.run_assistant import run_assistant_node
from assistants.langgraph.nodes.save_message import save_input_message_node
from assistants.langgraph.nodes.save_response import save_response_node
from assistants.langgraph.nodes.summarize_history import (
    should_summarize,
    summarize_history_node,
)

# Import state and cache types
from assistants.langgraph.prompt_context_cache import PromptContextCache

# Project specific imports
from assistants.langgraph.state import AssistantState
from langchain_core.language_models.chat_models import BaseChatModel  # For summary_llm
from langchain_core.runnables import Runnable

# Langchain core and specific components
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode, tools_condition
from services.rest_service import RestServiceClient

logger = logging.getLogger(__name__)


def route_after_assistant(state: AssistantState) -> Literal["tools", "save_response"]:
    """Determines the next step after the main assistant node runs.
    If tools are called, go to 'tools'. Otherwise, go to 'save_response'.
    """
    state.get("log_extra", {})
    messages = state.get("messages", [])
    msg_types = [type(m).__name__ for m in messages]
    logger.info(
        f"[route_after_assistant] ENTERED. Msgs: {len(messages)}, Types: {msg_types}"
    )
    if tools_condition(state) == "tools":
        return "tools"

    return "save_response"


def build_full_graph(
    tools: List[BaseTool],
    summary_llm: BaseChatModel,
    rest_client: RestServiceClient,
    prompt_context_cache: PromptContextCache,
    system_prompt_template: str,
    agent_runnable: Runnable,
    summarization_prompt: str,
    context_window_size: int,
    timeout: int = 30,
) -> CompiledGraph:
    """Builds the complete LangGraph state machine with database persistence.

    Flow:
    1. save_input - Save the incoming message to the database
    2. load_context - Load existing context (history, summary, facts)
    3. Conditional summarization if needed
    4. Main agent execution
    5. Tool execution if needed
    6. Save response to database
    7. Finalize processing (update message statuses, etc.)
    """
    logger.debug(
        f"Building graph with: tools={len(tools)}, "
        f"context_window={context_window_size}, "
        f"summary_prompt_len={len(summarization_prompt)}"
    )
    builder = StateGraph(AssistantState)

    # --- Nodes --- #

    # 1. save_input_message: Node to save the incoming message to the database
    bound_save_input_node = functools.partial(
        save_input_message_node,
        rest_client=rest_client,
    )
    builder.add_node("save_input", bound_save_input_node)

    # 2. load_context: Node to load conversation context from the database
    bound_load_context_node = functools.partial(
        load_context_node,
        rest_client=rest_client,
    )
    builder.add_node("load_context", bound_load_context_node)

    # 3. summarize: Node to summarize history and save via REST
    bound_summarize_node = functools.partial(
        summarize_history_node,
        summary_llm=summary_llm,
        rest_client=rest_client,
        summarization_prompt=summarization_prompt,
    )
    builder.add_node("summarize", bound_summarize_node)

    # 4. run_assistant: The core node running the agent logic (LLM call)
    bound_run_assistant_node = functools.partial(
        run_assistant_node, agent_runnable=agent_runnable, timeout=timeout
    )
    builder.add_node("assistant", bound_run_assistant_node)

    # 5. tools: Node that executes tools chosen by the assistant
    builder.add_node("tools", ToolNode(tools=tools))

    # 6. save_response: Node to save the assistant's response to the database
    bound_save_response_node = functools.partial(
        save_response_node,
        rest_client=rest_client,
    )
    builder.add_node("save_response", bound_save_response_node)

    # 7. finalize_processing: Node to finalize processing (update message statuses, etc.)
    bound_finalize_node = functools.partial(
        finalize_processing_node,
        rest_client=rest_client,
    )
    builder.add_node("finalize", bound_finalize_node)

    # --- Conditional Edge Function --- #
    bound_should_summarize_condition = functools.partial(
        should_summarize,
        system_prompt_template=system_prompt_template,
        max_tokens=context_window_size,
    )

    # --- Edges --- #

    # Start with saving the input message
    builder.add_edge(START, "save_input")

    # Then load the context
    builder.add_edge("save_input", "load_context")

    # After loading context, check if we need to summarize
    builder.add_conditional_edges(
        "load_context",
        bound_should_summarize_condition,
        {
            "summarize": "summarize",
            "assistant": "assistant",
        },
    )

    # After summarizing, go to the agent
    builder.add_edge("summarize", "assistant")

    # After the agent, either go to tools or save the response
    builder.add_conditional_edges(
        "assistant",
        route_after_assistant,
        {"tools": "tools", "save_response": "save_response"},
    )

    # After tools execution, check if we need to summarize again
    builder.add_conditional_edges(
        "tools",
        bound_should_summarize_condition,
        {
            "summarize": "summarize",
            "assistant": "assistant",
        },
    )

    # After saving the response, finalize processing
    builder.add_edge("save_response", "finalize")

    # After finalizing, end the graph
    builder.add_edge("finalize", END)

    # --- Compile Graph --- #
    return builder.compile()
