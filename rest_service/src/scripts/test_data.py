"""Test data initialization script"""

from models import Assistant, AssistantToolLink, TelegramUser
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from scripts.fixtures.assistant_tools import get_all_assistant_tools
from scripts.fixtures.assistants import get_all_assistants
from scripts.fixtures.tools import get_all_tools


async def create_test_data(db: AsyncSession) -> None:
    """Create test data in the database"""
    # Create assistants first to get their IDs
    assistants = get_all_assistants()
    for assistant in assistants:
        db.add(assistant)
    await db.commit()

    # Get writer assistant ID
    query = select(Assistant).where(Assistant.name == "writer")
    result = await db.execute(query)
    writer = result.scalar_one_or_none()
    if not writer:
        raise ValueError("Writer assistant not found in database")

    # Create tools with writer_id
    tools = get_all_tools(str(writer.id))
    for tool in tools:
        db.add(tool)
    await db.commit()

    # Create assistant-tool relationships
    assistant_tools = await get_all_assistant_tools(db)
    for assistant_tool in assistant_tools:
        db.add(assistant_tool)
    await db.commit()

    # Create test users
    test_users = [
        TelegramUser(telegram_id=625038902, username="vladmesh", is_active=True),
        TelegramUser(telegram_id=7192299, username="vladislav_mesh88k", is_active=True),
    ]

    for user_obj in test_users:
        db.add(user_obj)
    await db.commit()
