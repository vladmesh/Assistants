"""Queue statistics API routes for Redis queue observability."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

import crud.queue_message_log as queue_log_crud
from database import get_session
from models.queue_message_log import QueueDirection, QueueMessageLog

SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(prefix="/queue-stats", tags=["queue-stats"])


class QueueMessageLogCreate(BaseModel):
    """Request to create a queue message log entry."""

    queue_name: str
    direction: QueueDirection
    message_type: str
    payload: str
    correlation_id: str | None = None
    user_id: int | None = None
    source: str | None = None


class QueueMessageLogResponse(BaseModel):
    """Queue message log response."""

    id: UUID
    queue_name: str
    direction: QueueDirection
    correlation_id: str | None
    user_id: int | None
    message_type: str
    payload: str
    source: str | None
    processed: bool
    processed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class QueueStatsResponse(BaseModel):
    """Queue statistics response."""

    queue_name: str
    total_messages: int
    messages_last_hour: int
    messages_last_24h: int
    by_type: dict[str, int]
    by_source: dict[str, int]


@router.post(
    "/log", response_model=QueueMessageLogResponse, status_code=status.HTTP_201_CREATED
)
async def create_queue_log(
    log_in: QueueMessageLogCreate,
    session: SessionDep,
) -> QueueMessageLog:
    """Create a new queue message log entry."""
    db_log = await queue_log_crud.create(
        db=session,
        queue_name=log_in.queue_name,
        direction=log_in.direction,
        message_type=log_in.message_type,
        payload=log_in.payload,
        correlation_id=log_in.correlation_id,
        user_id=log_in.user_id,
        source=log_in.source,
    )
    return db_log


@router.get("/", response_model=list[QueueStatsResponse])
async def get_queue_stats(
    session: SessionDep,
) -> list[dict]:
    """Get statistics for all queues."""
    return await queue_log_crud.get_stats(db=session)


@router.get("/messages", response_model=list[QueueMessageLogResponse])
async def list_queue_messages(
    session: SessionDep,
    queue_name: Annotated[str | None, Query()] = None,
    user_id: Annotated[int | None, Query()] = None,
    correlation_id: Annotated[str | None, Query()] = None,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[QueueMessageLog]:
    """Get queue message logs with filters."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    return await queue_log_crud.get_list(
        db=session,
        queue_name=queue_name,
        user_id=user_id,
        correlation_id=correlation_id,
        since=since,
        limit=limit,
        offset=offset,
    )


@router.get("/messages/{log_id}", response_model=QueueMessageLogResponse)
async def get_queue_message(
    log_id: UUID,
    session: SessionDep,
) -> QueueMessageLog:
    """Get a specific queue message log."""
    db_log = await queue_log_crud.get(db=session, id=log_id)
    if not db_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue message log not found",
        )
    return db_log


@router.patch("/messages/{log_id}/processed", response_model=QueueMessageLogResponse)
async def mark_message_processed(
    log_id: UUID,
    session: SessionDep,
) -> QueueMessageLog:
    """Mark a queue message as processed."""
    db_log = await queue_log_crud.mark_processed(db=session, id=log_id)
    if not db_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Queue message log not found",
        )
    return db_log


@router.delete("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_old_logs(
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> dict:
    """Delete queue message logs older than N days."""
    count = await queue_log_crud.cleanup_old(db=session, days=days)
    return {"deleted": count}
