import base64
import binascii  # For catching base64 errors
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from shared_models.api_schemas import CheckpointCreate, CheckpointRead
from sqlmodel.ext.asyncio.session import AsyncSession  # Use AsyncSession

# Use absolute imports from src/
from crud import checkpoint as checkpoint_crud  # Import specific module
from database import get_session  # Import directly

SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(prefix="/checkpoints", tags=["checkpoints"])


@router.post(
    "/{thread_id}", response_model=CheckpointRead, status_code=status.HTTP_201_CREATED
)
async def save_checkpoint(
    thread_id: str,
    checkpoint_in: CheckpointCreate,
    db: SessionDep,
) -> Any:
    if thread_id != checkpoint_in.thread_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Thread ID in path does not match thread ID in body.",
        )
    try:
        checkpoint_data = base64.b64decode(checkpoint_in.checkpoint_data_base64)
    except (TypeError, binascii.Error) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 encoding for checkpoint data.",
        ) from exc

    # Simple approach: always create a new checkpoint
    db_checkpoint = await checkpoint_crud.create_checkpoint(
        db=db,
        thread_id=thread_id,
        checkpoint_data=checkpoint_data,
        checkpoint_metadata=checkpoint_in.checkpoint_metadata,
    )

    # Re-encode blob to base64 for the response
    response_data = CheckpointRead(
        id=db_checkpoint.id,
        thread_id=db_checkpoint.thread_id,
        checkpoint_data_base64=base64.b64encode(db_checkpoint.checkpoint_blob).decode(
            "utf-8"
        ),
        checkpoint_metadata=db_checkpoint.checkpoint_metadata,
        created_at=db_checkpoint.created_at,
        updated_at=db_checkpoint.updated_at,
    )
    return response_data


@router.get("/{thread_id}", response_model=CheckpointRead)
async def read_latest_checkpoint(thread_id: str, db: SessionDep) -> Any:
    db_checkpoint = await checkpoint_crud.get_latest_checkpoint(
        db=db, thread_id=thread_id
    )
    if db_checkpoint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checkpoint not found for this thread",
        )

    # Re-encode blob to base64 for the response
    response_data = CheckpointRead(
        id=db_checkpoint.id,
        thread_id=db_checkpoint.thread_id,
        checkpoint_data_base64=base64.b64encode(db_checkpoint.checkpoint_blob).decode(
            "utf-8"
        ),
        checkpoint_metadata=db_checkpoint.checkpoint_metadata,
        created_at=db_checkpoint.created_at,
        updated_at=db_checkpoint.updated_at,
    )
    return response_data
