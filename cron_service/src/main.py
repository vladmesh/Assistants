from scheduler import start_scheduler
import logging

logger = logging.getLogger(__name__)


def main():
    logger.info("Запускаем Cron Service...")
    start_scheduler()


if __name__ == "__main__":
    main()
