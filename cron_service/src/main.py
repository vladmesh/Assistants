from shared_models import LogEventType, configure_logging, get_logger

from config import settings
from scheduler import start_scheduler

# Configure logging
configure_logging(
    service_name="cron_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)
logger = get_logger(__name__)


def main():
    logger.info("Starting Cron Service", event_type=LogEventType.STARTUP)
    start_scheduler()


if __name__ == "__main__":
    main()
