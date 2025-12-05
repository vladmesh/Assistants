import logging
from uuid import UUID

from shared_models.api_schemas import ToolCreate, ToolUpdate
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.assistant import Tool, ToolType

logger = logging.getLogger(__name__)


async def get_tool(db: AsyncSession, tool_id: UUID) -> Tool | None:
    """Get a tool by its ID."""
    tool = await db.get(Tool, tool_id)
    return tool


async def get_tools(db: AsyncSession, skip: int = 0, limit: int = 100) -> list[Tool]:
    """Get a list of tools with pagination."""
    query = select(Tool).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_tool_by_name(db: AsyncSession, name: str) -> Tool | None:
    """Get a tool by its unique name."""
    query = select(Tool).where(Tool.name == name)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_tool(db: AsyncSession, tool_in: ToolCreate) -> Tool:
    """Create a new tool."""
    # Check if tool with the same name already exists
    existing_tool = await get_tool_by_name(db, tool_in.name)
    if existing_tool:
        logger.warning(f"Attempted to create tool with existing name: {tool_in.name}")
        raise ValueError(f"Tool with name '{tool_in.name}' already exists.")

    # Validate ToolType enum
    try:
        tool_type_enum = ToolType(tool_in.tool_type)
    except ValueError as exc:
        logger.error(f"Invalid tool_type value: {tool_in.tool_type}")
        raise ValueError(f"Invalid tool type: {tool_in.tool_type}") from exc

    tool_data = tool_in.model_dump()
    tool_data["tool_type"] = tool_type_enum  # Use the enum member

    db_tool = Tool(**tool_data)
    db.add(db_tool)
    await db.commit()
    await db.refresh(db_tool)
    logger.info(f"Tool created with ID: {db_tool.id}, Name: {db_tool.name}")
    return db_tool


async def update_tool(
    db: AsyncSession, tool_id: UUID, tool_in: ToolUpdate
) -> Tool | None:
    """Update an existing tool."""
    db_tool = await get_tool(db, tool_id)
    if not db_tool:
        logger.warning(f"Attempted to update non-existent tool ID: {tool_id}")
        return None

    update_data = tool_in.model_dump(exclude_unset=True)

    # Check for name conflict if name is being updated
    if "name" in update_data and update_data["name"] != db_tool.name:
        existing_tool = await get_tool_by_name(db, update_data["name"])
        if existing_tool:
            logger.warning(
                f"Attempted to update tool name to existing name: {update_data['name']}"
            )
            raise ValueError(f"Tool with name '{update_data['name']}' already exists.")

    # Validate tool_type if present
    if "tool_type" in update_data and update_data["tool_type"] is not None:
        try:
            update_data["tool_type"] = ToolType(update_data["tool_type"])
        except ValueError as exc:
            logger.error(
                "Invalid tool_type value during update: %s",
                update_data["tool_type"],
            )
            raise ValueError(f"Invalid tool type: {update_data['tool_type']}") from exc

    # Update model fields
    for key, value in update_data.items():
        setattr(db_tool, key, value)

    db.add(db_tool)  # Add to session to track changes
    await db.commit()
    await db.refresh(db_tool)
    logger.info(f"Tool updated with ID: {db_tool.id}")
    return db_tool


async def delete_tool(db: AsyncSession, tool_id: UUID) -> bool:
    """Delete a tool by its ID."""
    db_tool = await get_tool(db, tool_id)
    if not db_tool:
        logger.warning(f"Attempted to delete non-existent tool ID: {tool_id}")
        return False

    await db.delete(db_tool)
    await db.commit()
    logger.info(f"Tool deleted with ID: {tool_id}")
    return True
