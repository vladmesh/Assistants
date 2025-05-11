from typing import List, Optional
from uuid import UUID

# Placeholder for CRUD operations, to be created in crud/message.py
import crud.message as message_crud  # This line should refer to the new name
import structlog
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.message import Message  # For response_model
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import MessageCreate, MessageRead, MessageUpdate

logger = structlog.get_logger()
router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message_endpoint(
    message_in: MessageCreate, session: AsyncSession = Depends(get_session)
) -> Message:
    logger.info(
        "Creating new message", role=message_in.role, user_id=message_in.user_id
    )
    db_message = await message_crud.create(db=session, obj_in=message_in)  # Use .create
    return db_message


@router.get("/", response_model=List[MessageRead])
async def list_messages_endpoint(
    user_id: Optional[int] = Query(None),
    assistant_id: Optional[UUID] = Query(None),
    id_gt: Optional[int] = Query(
        None, description="Filter for messages with ID greater than this value"
    ),
    id_lt: Optional[int] = Query(
        None, description="Filter for messages with ID less than this value"
    ),
    role: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(
        None, alias="status"
    ),  # Renamed to avoid conflict with status_code
    summary_id: Optional[int] = Query(None),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0),
    sort_by: str = Query(default="id", description="Fields to sort by: id, timestamp"),
    sort_order: str = Query(default="asc", description="Sort order: asc, desc"),
    session: AsyncSession = Depends(get_session),
) -> List[Message]:
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
async def get_message_endpoint(
    message_id: int, session: AsyncSession = Depends(get_session)
) -> Message:
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
    session: AsyncSession = Depends(get_session),
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
