from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from shared_models.api_schemas import (
    MessageCreate,
    MessageRead,
    MessageUpdate,
)
from sqlmodel.ext.asyncio.session import AsyncSession

# Placeholder for CRUD operations, to be created in crud/message.py
import crud.message as message_crud  # This line should refer to the new name
from database import get_session
from models.message import Message  # For response_model

logger = structlog.get_logger()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message_endpoint(
    message_in: MessageCreate, session: SessionDep
) -> Message:
    logger.info(
        "Creating new message", role=message_in.role, user_id=message_in.user_id
    )
    db_message = await message_crud.create(db=session, obj_in=message_in)  # Use .create
    return db_message


@router.get("/", response_model=list[MessageRead])
async def list_messages_endpoint(
    session: SessionDep,
    user_id: Annotated[int | None, Query()] = None,
    assistant_id: Annotated[UUID | None, Query()] = None,
    id_gt: Annotated[
        int | None,
        Query(description="Filter for messages with ID greater than this value"),
    ] = None,
    id_lt: Annotated[
        int | None,
        Query(description="Filter for messages with ID less than this value"),
    ] = None,
    role: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    summary_id: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(le=1000)] = 100,
    offset: Annotated[int, Query()] = 0,
    sort_by: Annotated[
        str, Query(description="Fields to sort by: id, timestamp")
    ] = "id",
    sort_order: Annotated[
        str, Query(description="Sort order: asc, desc")
    ] = "asc",
) -> list[Message]:
    logger.info(
        "Listing messages",
        user_id=user_id,
        assistant_id=assistant_id,
        limit=limit,
        offset=offset,
    )
    messages = await message_crud.get_multi(
        db=session,
        user_id=user_id,
        assistant_id=assistant_id,
        id_gt=id_gt,
        id_lt=id_lt,
        role=role,
        status=status_filter,  # Passed as status to CRUD
        summary_id=summary_id,
        skip=offset,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return messages


@router.get("/{message_id}", response_model=MessageRead)
async def get_message_endpoint(message_id: int, session: SessionDep) -> Message:
    logger.info("Getting message by ID", message_id=message_id)
    db_message = await message_crud.get(db=session, id=message_id)
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    return db_message


@router.patch("/{message_id}", response_model=MessageRead)
async def update_message_endpoint(
    message_id: int,
    message_in: MessageUpdate,
    session: SessionDep,
) -> Message:
    print(f"DEBUG - Received update request with raw data: {message_in}")
    # Использовать exclude_unset=True вместо exclude_none=True
    update_data = message_in.model_dump(exclude_unset=True)
    print(f"DEBUG - Parsed update data: {update_data}")

    logger.info("Updating message", message_id=message_id, update_data=update_data)
    db_message = await message_crud.get(db=session, id=message_id)
    if not db_message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    updated_message = await message_crud.update(
        db=session, db_obj=db_message, obj_in=message_in
    )
    return updated_message
