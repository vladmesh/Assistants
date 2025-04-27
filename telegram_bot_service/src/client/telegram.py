import json
from typing import Any, Dict, List, Optional

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

        try:
            async with self.session.post(url, **kwargs) as response:
                response.raise_for_status()
                result = await response.json()

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

    async def send_message(
        self, chat_id: int, text: str, parse_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send message to chat."""
        logger.info(
            "Sending message", chat_id=chat_id, text=text, parse_mode=parse_mode
        )
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return await self._make_request("sendMessage", json=payload)

    async def send_message_with_inline_keyboard(
        self, chat_id: int, text: str, keyboard: List[List[Dict[str, str]]]
    ) -> None:
        """Send message with inline keyboard."""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "reply_markup": json.dumps({"inline_keyboard": keyboard}),
        }
        try:
            async with self.session.post(url, json=payload) as response:
                response.raise_for_status()
                logger.info(
                    "Message with inline keyboard sent", chat_id=chat_id, text=text
                )
        except aiohttp.ClientError as e:
            logger.error(
                "Error sending message with inline keyboard",
                chat_id=chat_id,
                error=str(e),
            )

    async def answer_callback_query(
        self, callback_query_id: str, text: Optional[str] = None
    ) -> None:
        """Answer callback query to remove the loading state on the button."""
        url = f"{self.base_url}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
            # payload['show_alert'] = False # Optional: show alert instead of toast

        try:
            async with self.session.post(url, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
                if result.get("ok"):
                    pass
                else:
                    logger.warning(
                        "Failed to answer callback query",
                        query_id=callback_query_id,
                        response=result,
                    )
        except aiohttp.ClientError as e:
            logger.error(
                "Error answering callback query",
                query_id=callback_query_id,
                error=str(e),
            )

    async def get_updates(
        self, offset: int = 0, timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """Get updates from Telegram."""
        result = await self._make_request(
            "getUpdates",
            json={
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": ["message", "callback_query"],
            },
        )
        return result if isinstance(result, list) else []
