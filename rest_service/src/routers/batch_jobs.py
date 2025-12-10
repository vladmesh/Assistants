"""BatchJob API routes for memory extraction tracking."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

import crud.batch_job as batch_job_crud
from database import get_session
from models.batch_job import BatchJob

logger = structlog.get_logger()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(prefix="/batch-jobs", tags=["batch-jobs"])


class BatchJobCreate(BaseModel):
    """Request to create a batch job."""

    batch_id: str
    user_id: int
    assistant_id: UUID | None = None
    job_type: str = "memory_extraction"
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    messages_processed: int = 0


class BatchJobStatusUpdate(BaseModel):
    """Request to update batch job status."""

    status: str
    facts_extracted: int | None = None
    error_message: str | None = None


class BatchJobResponse(BaseModel):
    """Batch job response."""

    id: UUID
    batch_id: str
    user_id: int
    assistant_id: UUID | None
    job_type: str
    status: str
    provider: str
    model: str
    messages_processed: int
    facts_extracted: int
    error_message: str | None

    class Config:
        from_attributes = True


@router.post("/", response_model=BatchJobResponse, status_code=status.HTTP_201_CREATED)
async def create_batch_job(
    job_in: BatchJobCreate,
    session: SessionDep,
) -> BatchJob:
    """Create a new batch job record."""
    logger.info("Creating batch job", batch_id=job_in.batch_id, user_id=job_in.user_id)
    db_job = await batch_job_crud.create(
        db=session,
        batch_id=job_in.batch_id,
        user_id=job_in.user_id,
        assistant_id=job_in.assistant_id,
        job_type=job_in.job_type,
        provider=job_in.provider,
        model=job_in.model,
        messages_processed=job_in.messages_processed,
    )
    return db_job


@router.get("/pending", response_model=list[BatchJobResponse])
async def get_pending_jobs(
    session: SessionDep,
    job_type: Annotated[str, Query()] = "memory_extraction",
    limit: Annotated[int, Query(le=100)] = 100,
) -> list[BatchJob]:
    """Get all pending batch jobs for processing."""
    logger.info("Fetching pending batch jobs", job_type=job_type)
    jobs = await batch_job_crud.get_pending(db=session, job_type=job_type, limit=limit)
    return jobs


@router.get("/{job_id}", response_model=BatchJobResponse)
async def get_batch_job(
    job_id: UUID,
    session: SessionDep,
) -> BatchJob:
    """Get a specific batch job by ID."""
    db_job = await batch_job_crud.get(db=session, id=job_id)
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch job not found",
        )
    return db_job


@router.get("/by-batch-id/{batch_id}", response_model=BatchJobResponse)
async def get_batch_job_by_batch_id(
    batch_id: str,
    session: SessionDep,
) -> BatchJob:
    """Get a batch job by provider batch_id."""
    db_job = await batch_job_crud.get_by_batch_id(db=session, batch_id=batch_id)
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch job not found",
        )
    return db_job


@router.patch("/{job_id}", response_model=BatchJobResponse)
async def update_batch_job_status(
    job_id: UUID,
    status_update: BatchJobStatusUpdate,
    session: SessionDep,
) -> BatchJob:
    """Update batch job status."""
    logger.info("Updating batch job status", job_id=job_id, status=status_update.status)
    db_job = await batch_job_crud.get(db=session, id=job_id)
    if not db_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch job not found",
        )
    updated_job = await batch_job_crud.update_status(
        db=session,
        db_obj=db_job,
        status=status_update.status,
        facts_extracted=status_update.facts_extracted,
        error_message=status_update.error_message,
    )
    return updated_job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch_job(
    job_id: UUID,
    session: SessionDep,
) -> None:
    """Delete a batch job."""
    logger.info("Deleting batch job", job_id=job_id)
    deleted = await batch_job_crud.delete(db=session, id=job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch job not found",
        )
