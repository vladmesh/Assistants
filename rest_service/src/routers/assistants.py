from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from shared_models.api_schemas import (
    AssistantCreate,
    AssistantRead,
    AssistantReadSimple,
    AssistantUpdate,
)
from sqlmodel.ext.asyncio.session import AsyncSession

import crud.assistant as assistant_crud  # Import the CRUD module
from database import get_session
from models.assistant import Assistant  # Keep model import for response_model

logger = structlog.get_logger()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter()


@router.get("/assistants/", response_model=list[AssistantReadSimple])
async def list_assistants(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
) -> list[Assistant]:
    """Get a list of all assistants"""
    logger.info("Listing assistants", skip=skip, limit=limit)
    assistants = await assistant_crud.get_assistants(db=session, skip=skip, limit=limit)
    logger.info(f"Found {len(assistants)} assistants")
    return assistants


@router.get("/assistants/{assistant_id}", response_model=AssistantRead)
async def get_assistant(assistant_id: UUID, session: SessionDep) -> Assistant:
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
    "/assistants/",
    response_model=AssistantReadSimple,
    status_code=status.HTTP_201_CREATED,
)
async def create_assistant(
    assistant_in: AssistantCreate, session: SessionDep
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
    except ValueError as exc:
        logger.error("Failed to create assistant due to invalid type", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception("Failed to create assistant due to unexpected error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.put("/assistants/{assistant_id}", response_model=AssistantRead)
async def update_assistant(
    assistant_id: UUID,
    assistant_update: AssistantUpdate,
    session: SessionDep,
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
    except ValueError as exc:
        logger.error(
            "Failed to update assistant due to invalid type",
            assistant_id=str(assistant_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        logger.exception(
            "Failed to update assistant due to unexpected error",
            assistant_id=str(assistant_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.delete("/assistants/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(assistant_id: UUID, session: SessionDep) -> None:
    """Delete an assistant"""
    logger.info("Attempting to delete assistant", assistant_id=str(assistant_id))
    try:
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
    except ValueError as exc:
        # Catch the ValueError raised by CRUD on IntegrityError
        logger.warning(
            f"Deletion conflict for assistant {assistant_id}: {exc}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except Exception as exc:
        # Catch any other unexpected errors
        logger.exception(
            f"Unexpected error deleting assistant {assistant_id}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during deletion.",
        ) from exc
