import os
import random
import sys
from collections.abc import AsyncGenerator
from uuid import UUID

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from config import Settings, settings
from database import get_session
from main import app  # Assuming your FastAPI app is defined in main.py
from models.assistant import Assistant
from models.user import TelegramUser

# Load test settings
TEST_SETTINGS = Settings(_env_file=".env.test")

# Internal service-to-service auth: pin a known token on the app and send the
# matching header from the test client so the auth middleware lets requests in.
INTERNAL_TEST_TOKEN = (
    os.environ.get("INTERNAL_API_TOKEN") or "integration-test-internal-token"
)
settings.INTERNAL_API_TOKEN = INTERNAL_TEST_TOKEN

# Проверка наличия переменной ASYNC_DATABASE_URL
DATABASE_URL = os.environ.get("ASYNC_DATABASE_URL")
if not DATABASE_URL:
    print(
        "ERROR: ASYNC_DATABASE_URL environment variable is not set. "
        "Tests cannot run without database connection."
    )
    sys.exit(1)


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test engine for each test (shares the per-test event loop)."""
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    yield engine

    # Close engine at the end of the session
    await engine.dispose()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database(test_engine):
    """Create the database tables before each test and drop them after."""
    # Пересоздаем все таблицы для каждого теста
    async with test_engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    yield

    # Таблицы будут удалены перед следующим тестом, так что очистка здесь не обязательна


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test function, ensuring cleanup."""
    # Create a new session for each test
    session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
        class_=AsyncSession,
    )

    async with session_factory() as session:
        try:
            # Begin a transaction
            yield session
        finally:
            # Always rollback at the end to ensure clean state
            await session.rollback()
            await session.close()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient for making requests to the test application."""

    # Override the get_session dependency with our test session
    def get_session_override() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_session] = get_session_override

    # Create a new client for each test
    async with AsyncClient(
        app=app,
        base_url="http://test",
        headers={"X-Internal-Token": INTERNAL_TEST_TOKEN},
    ) as async_client:
        yield async_client

    # Clear dependency overrides after test
    app.dependency_overrides.clear()


# Add fixtures for test data
@pytest_asyncio.fixture(scope="function")
async def test_user_id(db_session: AsyncSession) -> int:
    """Create a test user and return its ID."""
    # Создаем пользователя с уникальным telegram_id для избежания конфликтов
    telegram_id = 10000 + random.randint(1, 99999)
    user = TelegramUser(telegram_id=telegram_id, username="testuser")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


@pytest_asyncio.fixture(scope="function")
async def test_secretary_id(db_session: AsyncSession) -> UUID:
    """Create a test secretary assistant and return its ID."""
    # Create a secretary specifically for this test
    secretary = Assistant(
        name="Test Secretary Fixture",
        is_secretary=True,
        model="gpt-test-fixture",
        instructions="Fixture instructions",
        assistant_type="llm",
    )
    db_session.add(secretary)
    await db_session.commit()
    await db_session.refresh(secretary)
    return secretary.id
