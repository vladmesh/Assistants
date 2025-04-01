import pytest
from client.rest import RestClient
from client.telegram import TelegramClient
from config.settings import settings
from redis import asyncio as aioredis


@pytest.mark.asyncio
async def test_smoke():
    """Smoke test to verify basic service functionality."""
    # Test settings loading
    assert settings.telegram_token, "Telegram token should be set"
    assert settings.redis_host, "Redis host should be set"
    assert settings.rest_service_url, "REST service URL should be set"

    # Test Redis connection
    redis = aioredis.from_url(settings.redis_url, **settings.redis_settings)
    try:
        await redis.ping()
    finally:
        await redis.close()

    # Test clients initialization
    async with TelegramClient() as telegram, RestClient() as rest:
        assert telegram.base_url, "Telegram client should be initialized"
        assert rest.base_url, "REST client should be initialized"
