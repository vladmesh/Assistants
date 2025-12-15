import asyncio
import signal
from http.server import HTTPServer

import aiohttp
from redis import asyncio as aioredis
from shared_models import LogEventType, get_logger

from clients.rest import RestClient
from clients.telegram import TelegramClient
from config.settings import settings
from metrics import start_metrics_server
from services.response_processor import handle_assistant_responses

from .dispatcher import dispatch_update
from .polling import run_polling

logger = get_logger(__name__)


class BotLifecycle:
    """Manages the bot's startup, running tasks, and shutdown."""

    def __init__(self) -> None:
        self._telegram_client: TelegramClient | None = None
        self._rest_client: RestClient | None = None
        self._redis_client: aioredis.Redis | None = None
        self._metrics_server: HTTPServer | None = None
        self._tasks: list[asyncio.Task] = []
        self._should_stop = asyncio.Event()

    async def _initialize_clients(self) -> None:
        """Initialize external service clients and their sessions."""
        logger.info("Initializing clients...")

        # Start metrics server
        self._metrics_server = start_metrics_server(port=settings.metrics_port)
        logger.info("Metrics server started", port=settings.metrics_port)

        self._telegram_client = TelegramClient()
        self._rest_client = RestClient()

        # Создаем сессии для клиентов
        # TODO: Consider a shared session if beneficial
        try:
            self._telegram_client.session = aiohttp.ClientSession()
            logger.info("aiohttp session created for TelegramClient")
            self._rest_client.session = aiohttp.ClientSession()
            logger.info("aiohttp session created for RestClient")
        except Exception as e:
            logger.error(
                "Failed to create aiohttp sessions", error=str(e), exc_info=True
            )
            raise  # Stop startup if session creation fails

        self._redis_client = aioredis.from_url(
            settings.redis_url, **settings.redis_settings
        )
        # Test connections (optional but recommended)
        try:
            bot_info = await self._telegram_client._make_request("getMe")
            logger.info(
                "Telegram connection verified", bot_username=bot_info.get("username")
            )
            await (
                self._rest_client.ping()
            )  # Assuming a ping endpoint exists or implement one
            await self._redis_client.ping()
            logger.info("Clients initialized and connections verified.")
        except Exception as e:
            logger.error(
                "Failed to initialize or connect clients", error=str(e), exc_info=True
            )
            raise  # Re-raise to stop startup

    async def _start_tasks(self) -> None:
        """Create and start background tasks."""
        if not (self._telegram_client and self._rest_client and self._redis_client):
            logger.error("Clients not initialized before starting tasks.")
            return

        logger.info("Starting background tasks...")

        # Task for polling Telegram updates and dispatching them
        polling_task = asyncio.create_task(
            run_polling(
                self._telegram_client,
                self._rest_client,
                self._should_stop,
                dispatch_update,
            )
        )
        self._tasks.append(polling_task)
        logger.info("Polling task created.")

        # Task for handling responses from the assistant queue
        response_handler_task = asyncio.create_task(
            handle_assistant_responses(self._telegram_client, self._redis_client)
        )
        self._tasks.append(response_handler_task)
        logger.info("Response handler task created.")

        logger.info(f"{len(self._tasks)} tasks started.")

    async def _shutdown(self, signal_name: str = "") -> None:
        """Gracefully shut down the application."""
        if self._should_stop.is_set():
            return  # Avoid duplicate shutdowns
        logger.warning(
            f"Shutdown triggered by {signal_name}. Initiating graceful shutdown..."
        )
        self._should_stop.set()  # Signal polling loop to stop

        # Cancel running tasks
        logger.info(f"Cancelling {len(self._tasks)} tasks...")
        for task in self._tasks:
            if not task.done():
                task.cancel()
        # Wait for tasks to finish cancelling
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("All tasks cancelled or finished.")

        # Close client connections
        if self._telegram_client and self._telegram_client.session:
            await self._telegram_client.session.close()
            logger.info("Telegram client session closed.")
        if self._rest_client and self._rest_client.session:
            await self._rest_client.session.close()
            logger.info("REST client session closed.")
        if self._redis_client:
            await self._redis_client.close()
            logger.info("Redis client connection closed.")

        if self._metrics_server:
            self._metrics_server.shutdown()
            logger.info("Metrics server shut down.")

        logger.warning("Shutdown complete.")

    def _setup_signal_handlers(self) -> None:
        """Set up handlers for termination signals."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, lambda s=sig.name: asyncio.create_task(self._shutdown(s))
            )
        logger.info(
            "Signal handlers set",
            signals=[signal.SIGINT.name, signal.SIGTERM.name],
        )

    async def run(self) -> None:
        """Initialize, set up signals, start tasks, and run forever."""
        try:
            await self._initialize_clients()
            self._setup_signal_handlers()
            await self._start_tasks()

            # Keep running until shutdown signal is received
            # We wait on the tasks themselves, or use the event if tasks finish early
            if self._tasks:
                done, pending = await asyncio.wait(
                    self._tasks, return_when=asyncio.FIRST_COMPLETED
                )
                # If a task finished (possibly with error), log it and trigger shutdown
                for task in done:
                    try:
                        task.result()  # Check for exceptions
                        logger.info(f"Task {task.get_name()} finished unexpectedly.")
                    except asyncio.CancelledError:
                        logger.info(f"Task {task.get_name()} was cancelled.")
                    except Exception as e:
                        logger.error(
                            f"Task {task.get_name()} failed: {e}", exc_info=True
                        )
                if not self._should_stop.is_set():
                    await self._shutdown(
                        "TaskCompletion"
                    )  # Trigger shutdown if not already happening

            else:
                logger.warning("No tasks were started. Bot will exit.")

        except Exception as e:
            logger.critical(
                "Critical error during bot execution", error=str(e), exc_info=True
            )
        finally:
            # Ensure shutdown runs even if startup fails partially
            if not self._should_stop.is_set():
                await self._shutdown("RunFinally")


async def run_bot() -> None:
    """Entry point function to run the bot."""
    # Logging is already configured in main.py
    logger.info("Starting Telegram Bot Service", event_type=LogEventType.STARTUP)
    lifecycle = BotLifecycle()
    await lifecycle.run()
