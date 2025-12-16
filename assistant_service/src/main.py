import asyncio
import signal

from dotenv import load_dotenv
from shared_models import LogEventType, configure_logging, get_logger

from config.settings import get_settings
from metrics import start_metrics_server, update_dlq_metrics
from orchestrator import AssistantOrchestrator

load_dotenv()

# Configure logging early
settings = get_settings()
configure_logging(
    service_name="assistant_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)
logger = get_logger(__name__)


async def main():
    """Main entry point with preloading, background refresh, and graceful shutdown."""
    # Start metrics server
    metrics_server = start_metrics_server(port=settings.METRICS_PORT)
    logger.info("Metrics server started", port=settings.METRICS_PORT)

    service = AssistantOrchestrator(settings)
    listen_task = None
    shutdown_event = asyncio.Event()

    def _signal_handler(*_):
        logger.info(
            "Shutdown signal received",
            event_type=LogEventType.SHUTDOWN,
        )
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        logger.info("Starting assistant service", event_type=LogEventType.STARTUP)
        # Preload assignments before starting main loops
        await service.factory._preload_secretaries()

        # Start background tasks using the new method
        await service.factory.start_background_tasks()

        # Start main message listening task
        listen_task = asyncio.create_task(service.listen_for_messages())

        # Start DLQ metrics update task
        dlq_metrics_task = asyncio.create_task(
            update_dlq_metrics(service.input_stream, interval=60)
        )

        # Wait for any task to complete or shutdown signal
        tasks_to_wait = {
            listen_task,
            dlq_metrics_task,
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
                pass

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
        logger.info("Service interrupted", event_type=LogEventType.SHUTDOWN)
    except Exception as e:
        logger.exception(
            "Service encountered an unhandled error",
            event_type=LogEventType.ERROR,
            error=str(e),
        )
    finally:
        logger.info("Closing resources")
        # Stop background tasks using the new method
        await service.factory.stop_background_tasks()
        await service.factory.close()
        # Close the redis client which is part of the orchestrator
        await service.redis.aclose()
        # Stop metrics server
        metrics_server.shutdown()
        logger.info("Assistant service shut down", event_type=LogEventType.SHUTDOWN)


if __name__ == "__main__":
    asyncio.run(main())
