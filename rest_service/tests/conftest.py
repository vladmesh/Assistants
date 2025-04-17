import asyncio
from typing import AsyncGenerator, Generator
from uuid import UUID

import pytest_asyncio
from config import Settings
from database import get_session
from httpx import AsyncClient
from main import app  # Assuming your FastAPI app is defined in main.py
from models.assistant import Assistant
from models.user import TelegramUser
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool

# Load test settings (adjust path if needed)
TEST_SETTINGS = Settings(_env_file=".env.test")

# Use an in-memory SQLite database for testing
DATABASE_URL = "sqlite+aiosqlite:///./test.db"
# Alternative for synchronous tests if needed:
# SYNC_DATABASE_URL = "sqlite:///./test_sync.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True to see SQL queries
    connect_args={"check_same_thread": False},  # Needed for SQLite
    poolclass=StaticPool,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create the database tables before running tests and drop them after."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for each test function, ensuring cleanup."""
    async with engine.connect() as connection:
        # Begin a nested transaction (uses SAVEPOINT)
        await connection.begin_nested()
        # Then create the session based on this connection
        async with AsyncSession(connection, expire_on_commit=False) as session:
            yield session
            # Rollback the nested transaction. This effectively reverts
            # all changes made within the session, including commits
            # made within the test function or its fixtures if they use
            # the same session object.
            await connection.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient for making requests to the test application."""

    def get_session_override() -> AsyncSession:
        return db_session

    app.dependency_overrides[get_session] = get_session_override

    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client

    app.dependency_overrides.clear()


# Add fixtures for test data
@pytest_asyncio.fixture(scope="function")
async def test_user_id(db_session: AsyncSession) -> int:
    user = TelegramUser(telegram_id=12345, username="testuser")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.id


@pytest_asyncio.fixture(scope="function")
async def test_secretary_id(db_session: AsyncSession) -> UUID:
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
