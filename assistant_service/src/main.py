import asyncio
from dotenv import load_dotenv
from config.logger import get_logger
from config.settings import get_settings
from orchestrator import AssistantOrchestrator

logger = get_logger(__name__)
load_dotenv()  # Load .env for API keys


async def main():
    """Main entry point."""
    try:
        settings = get_settings()
        service = AssistantOrchestrator(settings)
        await service.listen_for_messages()
    except Exception as e:
        logger.error("Service failed", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
