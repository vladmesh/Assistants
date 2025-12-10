import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from assistants.factory import AssistantFactory


class DummyRestClient:
    def __init__(self, updated_at):
        self._updated_at = updated_at

    async def get_assistant(self, _id: str):
        class Result:
            updated_at = self._updated_at

        return Result()


@pytest.mark.asyncio
async def test_check_and_update_uses_aware_datetimes(monkeypatch):
    factory: AssistantFactory = AssistantFactory.__new__(AssistantFactory)
    factory.rest_client = DummyRestClient(datetime.now(UTC) + timedelta(minutes=5))
    factory.logger = factory.logger if hasattr(factory, "logger") else None
    factory._assistant_cache = {}
    factory._cache_lock = asyncio.Lock()

    called = asyncio.Event()

    async def fake_get_assistant_by_id(_assistant_id, _user_id=None):
        called.set()

    factory.get_assistant_by_id = fake_get_assistant_by_id  # type: ignore[attr-defined]

    await factory._check_and_update_assistant_cache(
        (uuid4(), "user"), instance=object(), loaded_at=datetime.now(UTC)
    )

    assert called.is_set()


@pytest.mark.asyncio
async def test_check_and_update_errors_on_naive():
    factory: AssistantFactory = AssistantFactory.__new__(AssistantFactory)
    factory.rest_client = DummyRestClient(datetime.now(UTC))
    factory.logger = factory.logger if hasattr(factory, "logger") else None
    factory._assistant_cache = {}
    factory._cache_lock = asyncio.Lock()

    called = False

    async def fake_get_assistant_by_id(_assistant_id, _user_id=None):
        nonlocal called
        called = True

    factory.get_assistant_by_id = fake_get_assistant_by_id  # type: ignore[attr-defined]

    await factory._check_and_update_assistant_cache(
        (uuid4(), "user"), instance=object(), loaded_at=datetime.now()
    )

    assert called is False
