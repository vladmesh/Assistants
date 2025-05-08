import logging
from typing import List
from uuid import UUID

from models.assistant import Assistant, AssistantToolLink, Tool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# from schemas import AssistantToolLinkCreate
from shared_models.api_schemas import AssistantToolLinkCreate

logger = logging.getLogger(__name__)


async def get_assistant_tools(db: AsyncSession, assistant_id: UUID) -> List[Tool]:
    """Get all tools linked to a specific assistant."""
    # First, check if the assistant exists
    assistant = await db.get(Assistant, assistant_id)
    if not assistant:
        logger.warning(f"Assistant not found when fetching tools: {assistant_id}")
        raise ValueError("Assistant not found")

    query = (
        select(Tool)
        .join(AssistantToolLink, AssistantToolLink.tool_id == Tool.id)
        .where(AssistantToolLink.assistant_id == assistant_id)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def add_tool_to_assistant(
    db: AsyncSession, link_in: AssistantToolLinkCreate
) -> AssistantToolLink:
    """Link a tool to an assistant."""
    # Check if assistant exists
    assistant = await db.get(Assistant, link_in.assistant_id)
    if not assistant:
        logger.error(
            f"Assistant not found when adding tool link: {link_in.assistant_id}"
        )
        raise ValueError("Assistant not found")

    # Check if tool exists
    tool = await db.get(Tool, link_in.tool_id)
    if not tool:
        logger.error(f"Tool not found when adding tool link: {link_in.tool_id}")
        raise ValueError("Tool not found")

    # Check if the link already exists
    result = await db.execute(
        select(AssistantToolLink)
        .where(AssistantToolLink.assistant_id == link_in.assistant_id)
        .where(AssistantToolLink.tool_id == link_in.tool_id)
    )
    existing_link = result.one_or_none()
    if existing_link:
        logger.warning(
            f"Tool {link_in.tool_id} already linked to assistant {link_in.assistant_id}"
        )
        # Depending on requirements, could return the existing link or raise an error
        raise ValueError("Tool already linked to this assistant")

    db_link = AssistantToolLink.model_validate(link_in)
    db.add(db_link)
    await db.commit()
    await db.refresh(db_link)
    logger.info(f"Linked tool {link_in.tool_id} to assistant {link_in.assistant_id}")
    return db_link


async def remove_tool_from_assistant(
    db: AsyncSession, assistant_id: UUID, tool_id: UUID
) -> bool:
    """Unlink a tool from an assistant."""
    query = (
        select(AssistantToolLink)
        .where(AssistantToolLink.assistant_id == assistant_id)
        .where(AssistantToolLink.tool_id == tool_id)
    )
    result = await db.execute(query)
    link_to_delete = result.scalar_one_or_none()

    if not link_to_delete:
        logger.warning(
            f"Link not found for assistant {assistant_id} and tool {tool_id}"
        )
        return False

    await db.delete(link_to_delete)
    await db.commit()
    logger.info(f"Unlinked tool {tool_id} from assistant {assistant_id}")
    return True
