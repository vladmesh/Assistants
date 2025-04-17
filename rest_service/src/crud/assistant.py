import logging
from typing import List, Optional
from uuid import UUID

from models.assistant import Assistant, AssistantType
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# from schemas import AssistantCreate, AssistantUpdate  # Assuming schemas are defined
from shared_models.api_schemas import AssistantCreate, AssistantUpdate

logger = logging.getLogger(__name__)


async def get_assistant(db: AsyncSession, assistant_id: UUID) -> Optional[Assistant]:
    """Get an assistant by its ID, eagerly loading tools."""
    # Use select with options for loading relationships
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .options(selectinload(Assistant.tools))  # Eagerly load tools
    )
    assistant = result.scalar_one_or_none()
    # No need for db.get() or db.refresh()
    return assistant


async def get_assistants(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Assistant]:
    """Get a list of assistants with pagination."""
    query = select(Assistant).offset(skip).limit(limit)
    result = await db.execute(query)
    assistants = result.scalars().all()
    # Optionally load relationships if needed for the list view
    # for assistant in assistants:
    #     await db.refresh(assistant, ["tools"])
    return assistants


async def create_assistant(
    db: AsyncSession, assistant_in: AssistantCreate
) -> Assistant:
    """Create a new assistant."""
    # Ensure assistant_type is valid Enum member before creating
    try:
        assistant_type_enum = AssistantType(assistant_in.assistant_type)
    except ValueError:
        logger.error(f"Invalid assistant_type value: {assistant_in.assistant_type}")
        # Consider raising a specific exception or handling it as needed
        raise ValueError(f"Invalid assistant type: {assistant_in.assistant_type}")

    assistant_data = assistant_in.model_dump()
    assistant_data["assistant_type"] = assistant_type_enum  # Use the enum member

    db_assistant = Assistant(**assistant_data)
    db.add(db_assistant)
    await db.commit()
    await db.refresh(db_assistant)
    # Optionally refresh relationships if needed immediately after creation
    # await db.refresh(db_assistant, ["tools"])
    logger.info(f"Assistant created with ID: {db_assistant.id}")
    return db_assistant


async def update_assistant(
    db: AsyncSession, assistant_id: UUID, assistant_in: AssistantUpdate
) -> Optional[Assistant]:
    """Update an existing assistant."""
    db_assistant = await get_assistant(db, assistant_id)  # Reuse get_assistant
    if not db_assistant:
        logger.warning(f"Attempted to update non-existent assistant ID: {assistant_id}")
        return None

    assistant_data = assistant_in.model_dump(exclude_unset=True)

    # Handle assistant_type conversion if present in update data
    if (
        "assistant_type" in assistant_data
        and assistant_data["assistant_type"] is not None
    ):
        try:
            assistant_data["assistant_type"] = AssistantType(
                assistant_data["assistant_type"]
            )
        except ValueError:
            logger.error(
                f"Invalid assistant_type value during update: {assistant_data['assistant_type']}"
            )
            raise ValueError(
                f"Invalid assistant type: {assistant_data['assistant_type']}"
            )

    # Update model fields
    for key, value in assistant_data.items():
        setattr(db_assistant, key, value)

    db.add(db_assistant)  # Add to session to track changes
    await db.commit()
    await db.refresh(db_assistant)
    # Optionally refresh relationships
    # await db.refresh(db_assistant, ["tools"])
    logger.info(f"Assistant updated with ID: {db_assistant.id}")
    return db_assistant


async def delete_assistant(db: AsyncSession, assistant_id: UUID) -> bool:
    """Delete an assistant by its ID."""
    db_assistant = await get_assistant(db, assistant_id)  # Reuse get_assistant
    if not db_assistant:
        logger.warning(f"Attempted to delete non-existent assistant ID: {assistant_id}")
        return False

    await db.delete(db_assistant)
    await db.commit()
    logger.info(f"Assistant deleted with ID: {assistant_id}")
    return True
