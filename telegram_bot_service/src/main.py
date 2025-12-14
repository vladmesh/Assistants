import asyncio

from shared_models import LogEventType, configure_logging, get_logger

from bot.lifecycle import run_bot
from config.settings import settings

# Configure logging early
configure_logging(
    service_name="telegram_bot_service",
    log_level=settings.log_level,
    json_format=settings.log_json_format,
)
logger = get_logger(__name__)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info(
            "Application stopped by KeyboardInterrupt",
            event_type=LogEventType.SHUTDOWN,
        )
    except Exception as e:
        logger.critical(
            "Application failed to run",
            event_type=LogEventType.ERROR,
            error=str(e),
            exc_info=True,
        )
