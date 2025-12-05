import asyncio
from collections.abc import Callable
from typing import Any

import structlog

from clients.rest import RestClient
from clients.telegram import TelegramClient
from config.settings import settings

logger = structlog.get_logger()


async def run_polling(
    telegram: TelegramClient,
    rest: RestClient,  # rest нужен диспетчеру/хэндлерам
    stop_event: asyncio.Event,
    dispatcher_callback: Callable[..., Any],  # Функция диспетчера
) -> None:
    """Runs the main polling loop to get updates from Telegram."""
    logger.info("Starting polling loop...")
    last_update_id = 0

    while not stop_event.is_set():
        try:
            updates = await telegram.get_updates(offset=last_update_id + 1)

            if updates:
                logger.debug(f"Received {len(updates)} updates")
                for update in updates:
                    update_id = update.get("update_id")
                    if update_id:
                        last_update_id = max(last_update_id, update_id)

                    # Запускаем обработку обновления в отдельной задаче,
                    # чтобы не блокировать получение следующих обновлений
                    # Передаем нужные клиенты диспетчеру
                    asyncio.create_task(
                        dispatcher_callback(update=update, telegram=telegram, rest=rest)
                    )
            # Небольшая пауза перед следующим запросом, если не было обновлений
            # или после обработки пачки обновлений
            await asyncio.sleep(settings.update_interval)

        except asyncio.CancelledError:
            logger.info("Polling loop cancelled.")
            break  # Выходим из цикла при отмене
        except Exception as e:
            logger.error("Error in polling loop", error=str(e), exc_info=True)
            # Пауза перед повторной попыткой в случае ошибки
            await asyncio.sleep(settings.update_interval * 5)

    logger.warning("Polling loop stopped.")
