"""Database initialization and session management"""

from config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Create async engine
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

# Create session factory
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def drop_all_tables() -> None:
    """Drop and recreate public schema"""
    async with async_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


async def init_db(drop_tables: bool = False, create_tables: bool = False) -> None:
    """Initialize database with tables and test data

    Args:
        drop_tables: If True, drops and recreates public schema
        create_tables: If True, creates all tables from models
    """
    if drop_tables:
        await drop_all_tables()

    if create_tables:
        async with async_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    # Create test data
    # async with AsyncSessionLocal() as session:
    #    await create_test_data(session)


async def get_session() -> AsyncSession:
    """Get database session"""
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()
