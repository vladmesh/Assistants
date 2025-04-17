from typing import Any, List, Optional
from uuid import UUID

import crud.assistant as assistant_crud  # Import the CRUD module
import structlog
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from models.assistant import Assistant  # Keep model import for response_model
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import AssistantCreate, AssistantRead, AssistantUpdate

logger = structlog.get_logger()
router = APIRouter()


@router.get("/assistants/", response_model=List[AssistantRead])
async def list_assistants(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
) -> List[Assistant]:
    """Get a list of all assistants"""
    logger.info("Listing assistants", skip=skip, limit=limit)
    assistants = await assistant_crud.get_assistants(db=session, skip=skip, limit=limit)
    logger.info(f"Found {len(assistants)} assistants")
    return assistants


@router.get("/assistants/{assistant_id}", response_model=AssistantRead)
async def get_assistant(
    assistant_id: UUID, session: AsyncSession = Depends(get_session)
) -> Assistant:
    """Get an assistant by ID"""
    logger.info("Getting assistant by ID", assistant_id=str(assistant_id))
    assistant = await assistant_crud.get_assistant(
        db=session, assistant_id=assistant_id
    )
    if not assistant:
        logger.warning("Assistant not found", assistant_id=str(assistant_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found"
        )
    logger.info("Assistant found", assistant_id=str(assistant_id), name=assistant.name)
    return assistant


@router.post(
    "/assistants/", response_model=AssistantRead, status_code=status.HTTP_201_CREATED
)
async def create_assistant(
    assistant_in: AssistantCreate, session: AsyncSession = Depends(get_session)
) -> Assistant:
    """Create a new assistant"""
    logger.info(
        "Attempting to create assistant",
        name=assistant_in.name,
        type=assistant_in.assistant_type,
    )
    try:
        db_assistant = await assistant_crud.create_assistant(
            db=session, assistant_in=assistant_in
        )
        logger.info("Assistant created successfully", assistant_id=str(db_assistant.id))
        return db_assistant
    except ValueError as e:
        logger.error("Failed to create assistant due to invalid type", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create assistant due to unexpected error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/assistants/{assistant_id}", response_model=AssistantRead)
async def update_assistant(
    assistant_id: UUID,
    assistant_update: AssistantUpdate,
    session: AsyncSession = Depends(get_session),
) -> Assistant:
    """Update an assistant"""
    logger.info("Attempting to update assistant", assistant_id=str(assistant_id))
    try:
        updated_assistant = await assistant_crud.update_assistant(
            db=session, assistant_id=assistant_id, assistant_in=assistant_update
        )
        if updated_assistant is None:
            logger.warning(
                "Assistant not found for update", assistant_id=str(assistant_id)
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found"
            )
        logger.info(
            "Assistant updated successfully", assistant_id=str(updated_assistant.id)
        )
        return updated_assistant
    except ValueError as e:
        logger.error(
            "Failed to update assistant due to invalid type",
            assistant_id=str(assistant_id),
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(
            "Failed to update assistant due to unexpected error",
            assistant_id=str(assistant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/assistants/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: UUID, session: AsyncSession = Depends(get_session)
) -> None:
    """Delete an assistant"""
    logger.info("Attempting to delete assistant", assistant_id=str(assistant_id))
    deleted = await assistant_crud.delete_assistant(
        db=session, assistant_id=assistant_id
    )
    if not deleted:
        logger.warning(
            "Assistant not found for deletion", assistant_id=str(assistant_id)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found"
        )
    logger.info("Assistant deleted successfully", assistant_id=str(assistant_id))
    return None  # Return None for 204 No Content
