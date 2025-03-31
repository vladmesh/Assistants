from typing import Optional, Dict, Any, List
import aiohttp
import structlog
from config.settings import settings

logger = structlog.get_logger()


class TelegramClient:
    """Async client for Telegram Bot API."""

    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_token}"
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info("TelegramClient initialized", base_url=self.base_url)

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _make_request(self, method: str, **kwargs) -> Dict[str, Any]:
        """Make request to Telegram API."""
        if not self.session:
            raise RuntimeError(
                "Session is not initialized. Use 'async with' context manager."
            )

        url = f"{self.base_url}/{method}"
        logger.debug("Making request to Telegram", url=url, method=method, **kwargs)

        try:
            async with self.session.post(url, **kwargs) as response:
                response.raise_for_status()
                result = await response.json()
                logger.debug("Got response from Telegram", result=result)

                if not result.get("ok"):
                    error = result.get("description", "Unknown error")
                    logger.error("Telegram API error", error=error, method=method)
                    raise ValueError(f"Telegram API error: {error}")

                return result.get("result", {})

        except Exception as e:
            logger.error(
                "Telegram request error", method=method, error=str(e), exc_info=True
            )
            raise

    async def send_message(self, chat_id: int, text: str) -> Dict[str, Any]:
        """Send message to chat."""
        logger.info("Sending message", chat_id=chat_id, text=text)
        return await self._make_request(
            "sendMessage", json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        )

    async def get_updates(
        self, offset: int = 0, timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """Get updates from Telegram."""
        logger.debug("Getting updates", offset=offset)
        result = await self._make_request(
            "getUpdates",
            json={"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
        )
        return result if isinstance(result, list) else []
