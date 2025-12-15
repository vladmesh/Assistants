"""JobExecution API routes for cron job monitoring."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

import crud.job_execution as job_execution_crud
from database import get_session
from models.job_execution import JobExecution, JobStatus

SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(prefix="/job-executions", tags=["job-executions"])


class JobExecutionCreate(BaseModel):
    """Request to create a job execution record."""

    job_id: str
    job_name: str
    job_type: str
    scheduled_at: datetime
    user_id: int | None = None
    reminder_id: int | None = None


class JobExecutionUpdate(BaseModel):
    """Request to update job execution."""

    result: str | None = None


class JobExecutionFail(BaseModel):
    """Request to mark job as failed."""

    error: str
    error_traceback: str | None = None


class JobExecutionResponse(BaseModel):
    """Job execution response."""

    id: UUID
    job_id: str
    job_name: str
    job_type: str
    status: JobStatus
    scheduled_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    user_id: int | None
    reminder_id: int | None
    result: str | None
    error: str | None
    error_traceback: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class JobStatsResponse(BaseModel):
    """Job statistics response."""

    total: int
    completed: int
    failed: int
    running: int
    scheduled: int
    avg_duration_ms: int
    by_type: dict[str, dict[str, int]]


@router.post(
    "/", response_model=JobExecutionResponse, status_code=status.HTTP_201_CREATED
)
async def create_job_execution(
    job_in: JobExecutionCreate,
    session: SessionDep,
) -> JobExecution:
    """Create a new job execution record."""
    db_job = await job_execution_crud.create(
        db=session,
        job_id=job_in.job_id,
        job_name=job_in.job_name,
        job_type=job_in.job_type,
        scheduled_at=job_in.scheduled_at,
        user_id=job_in.user_id,
        reminder_id=job_in.reminder_id,
    )
    return db_job


@router.get("/", response_model=list[JobExecutionResponse])
async def list_job_executions(
    session: SessionDep,
    job_type: Annotated[str | None, Query()] = None,
    status: Annotated[JobStatus | None, Query()] = None,
    user_id: Annotated[int | None, Query()] = None,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobExecution]:
    """Get job executions with filters."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    return await job_execution_crud.get_list(
        db=session,
        job_type=job_type,
        status=status,
        user_id=user_id,
        since=since,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=JobStatsResponse)
async def get_job_stats(
    session: SessionDep,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> dict:
    """Get job execution statistics."""
    return await job_execution_crud.get_stats(db=session, hours=hours)


@router.get("/{execution_id}", response_model=JobExecutionResponse)
async def get_job_execution(
    execution_id: UUID,
    session: SessionDep,
) -> JobExecution:
    """Get a specific job execution."""
    db_job = await job_execution_crud.get(db=session, id=execution_id)
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job execution not found",
        )
    return db_job


@router.patch("/{execution_id}/start", response_model=JobExecutionResponse)
async def start_job_execution(
    execution_id: UUID,
    session: SessionDep,
) -> JobExecution:
    """Mark job as started."""
    db_job = await job_execution_crud.start(db=session, id=execution_id)
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job execution not found",
        )
    return db_job


@router.patch("/{execution_id}/complete", response_model=JobExecutionResponse)
async def complete_job_execution(
    execution_id: UUID,
    session: SessionDep,
    update: JobExecutionUpdate | None = None,
) -> JobExecution:
    """Mark job as completed."""
    result = update.result if update else None
    db_job = await job_execution_crud.complete(
        db=session, id=execution_id, result=result
    )
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job execution not found",
        )
    return db_job


@router.patch("/{execution_id}/fail", response_model=JobExecutionResponse)
async def fail_job_execution(
    execution_id: UUID,
    fail_data: JobExecutionFail,
    session: SessionDep,
) -> JobExecution:
    """Mark job as failed."""
    db_job = await job_execution_crud.fail(
        db=session,
        id=execution_id,
        error=fail_data.error,
        error_traceback=fail_data.error_traceback,
    )
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job execution not found",
        )
    return db_job


@router.delete("/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_old_executions(
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=30)] = 7,
) -> dict:
    """Delete job executions older than N days."""
    count = await job_execution_crud.cleanup_old(db=session, days=days)
    return {"deleted": count}
