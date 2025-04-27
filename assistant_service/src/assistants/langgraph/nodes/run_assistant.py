import asyncio
import time
from typing import Any, Dict

from assistants.langgraph.state import AssistantState
from config import logger
from langchain_core.runnables import Runnable
from utils.error_handler import MessageProcessingError


async def run_assistant_node(
    state: AssistantState, agent_runnable: Runnable, timeout: int = 30
) -> Dict[str, Any]:
    """Executes the core agent logic using the pre-configured agent_runnable."""
    print("Entering _run_assistant_node")

    # The self.agent_runnable implicitly calls _add_system_prompt_modifier
    # The state passed here ALREADY has messages filtered by the reducer.
    try:
        # Timeout logic implementation
        start_time = time.monotonic()
        task = asyncio.create_task(agent_runnable.ainvoke(state))
        done, pending = await asyncio.wait(
            [task], timeout=timeout, return_when=asyncio.FIRST_COMPLETED
        )

        if task in done:
            result = task.result()
            time.monotonic() - start_time
            return result
        else:
            # Timeout occurred
            task.cancel()
            try:
                await task  # Wait for cancellation to propagate
            except asyncio.CancelledError:
                logger.error(f"Agent runnable invocation timed out after {timeout}s.")
                raise MessageProcessingError(
                    f"Assistant processing timed out after {timeout}s."
                )
            except Exception as e:
                # Log unexpected errors during cancellation
                logger.exception(
                    f"Unexpected error during agent task cancellation: {e}",
                    exc_info=True,
                )
                raise MessageProcessingError(
                    f"Error during agent node timeout handling: {e}"
                ) from e

    except Exception as e:
        # Catch errors from ainvoke itself or timeout handling
        if not isinstance(e, MessageProcessingError):  # Avoid double wrapping
            logger.exception(
                "Error during agent runnable invocation or timeout handling.",
                exc_info=True,
            )
            raise MessageProcessingError(f"Error in agent node: {e}") from e
        else:
            raise e  # Re-raise MessageProcessingError
