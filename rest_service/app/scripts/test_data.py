"""Test data initialization script"""
from sqlmodel.ext.asyncio.session import AsyncSession
from app.scripts.fixtures.tools import get_all_tools
from app.scripts.fixtures.assistants import get_all_assistants
from app.models import TelegramUser

async def create_test_data(db: AsyncSession) -> None:
    """Create test data in the database"""
    # Create tools
    tools = get_all_tools()
    for tool in tools:
        db.add(tool)
    await db.commit()
    
    # Create assistants
    assistants = get_all_assistants()
    for assistant in assistants:
        db.add(assistant)
    await db.commit()
    
    # Create test users
    test_users = [
        TelegramUser(
            telegram_id=625038902,
            username="vladmesh",
            is_active=True
        ),
        TelegramUser(
            telegram_id=7192299,
            username="vladislav_mesh88k",
            is_active=True
        )
    ]
    
    for user_obj in test_users:
        db.add(user_obj)
    await db.commit() 