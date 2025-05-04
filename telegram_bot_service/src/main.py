import asyncio
import logging  # Keep for basicConfig potentially

import structlog

# Import the entry point from the bot lifecycle module
from bot.lifecycle import run_bot

# Configure logging here or ensure it's done in run_bot
# Keep basicConfig for initial setup if run_bot's config is complex
logger = structlog.get_logger()


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Application stopped by KeyboardInterrupt.")
    except Exception as e:
        logger.critical("Application failed to run.", error=str(e), exc_info=True)
