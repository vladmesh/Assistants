"""Assistant-Tool relationship fixtures for database initialization"""

from typing import List

from models.assistant import Assistant, AssistantToolLink, Tool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


async def create_secretary_tools(db: AsyncSession) -> list[AssistantToolLink]:
    """Create Secretary-Tool relationship fixtures"""
    # Get secretary assistant from DB
    query = select(Assistant).where(Assistant.is_secretary.is_(True))
    result = await db.execute(query)
    secretary = result.scalar_one_or_none()
    if not secretary:
        raise ValueError("Secretary assistant not found in database")

    # Get all tools from DB
    query = select(Tool)
    result = await db.execute(query)
    tools = result.scalars().all()
    if not tools:
        raise ValueError("No tools found in database")

    return [
        AssistantToolLink(assistant_id=secretary.id, tool_id=tool.id) for tool in tools
    ]


async def get_all_assistant_tools(db: AsyncSession) -> list[AssistantToolLink]:
    """Get all assistant-tool relationship fixtures"""
    return await create_secretary_tools(db)
