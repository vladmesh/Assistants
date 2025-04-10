import asyncio
import signal  # Add signal handling

from assistants.factory import AssistantFactory
from config.logger import get_logger
from config.settings import get_settings
from core.message_queue import MessageQueue
from dotenv import load_dotenv
from orchestrator import AssistantOrchestrator
from services.rest_service import (  # Ensure this is imported if needed elsewhere
    RestServiceClient,
)

logger = get_logger(__name__)
load_dotenv()  # Load .env for API keys


async def main():
    """Main entry point with preloading, background refresh, and graceful shutdown."""
    settings = get_settings()
    service = AssistantOrchestrator(settings)
    refresh_task = None
    listen_task = None
    shutdown_event = asyncio.Event()

    def _signal_handler(*_):
        logger.info("Shutdown signal received, initiating graceful shutdown...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        logger.info("Starting assistant service...")
        # Preload assignments before starting main loops
        await service.factory._preload_secretaries()

        # Start background tasks using the new method
        await service.factory.start_background_tasks()

        # Start main message listening task
        listen_task = asyncio.create_task(service.listen_for_messages())

        # Wait for any task to complete or shutdown signal
        tasks_to_wait = {
            listen_task,
            asyncio.create_task(shutdown_event.wait()),
        }
        done, pending = await asyncio.wait(
            tasks_to_wait,
            return_when=asyncio.FIRST_COMPLETED,
        )

        logger.info("Initiating task cancellation...")
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task  # Wait for cancellation
            except asyncio.CancelledError:
                logger.debug(f"Task {task.get_name()} cancelled successfully.")

        # Check for exceptions in completed tasks
        for task in done:
            if task.exception():
                exc = task.exception()
                logger.error(
                    f"Task {task.get_name()} completed with exception: {exc}",
                    exc_info=exc,
                )
                # Potentially re-raise or handle specific exceptions

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Service interrupted. Shutting down...")
    except Exception as e:
        logger.exception("Service encountered an unhandled error", error=e)
    finally:
        logger.info("Closing resources...")
        # Stop background tasks using the new method
        await service.factory.stop_background_tasks()
        await service.factory.close()
        await service.message_queue.close()
        logger.info("Assistant service shut down.")


if __name__ == "__main__":
    asyncio.run(main())
