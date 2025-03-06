import os
from dataclasses import dataclass


@dataclass
class BotConfig:
    token: str
    admin_ids: list[int]


def load_config() -> BotConfig:
    """Загружает конфигурацию бота из переменных окружения."""
    return BotConfig(
        token=os.getenv("TELEGRAM_TOKEN", ""),
        admin_ids=[int(id_) for id_ in os.getenv("ADMIN_IDS", "").split(",") if id_]
    ) 