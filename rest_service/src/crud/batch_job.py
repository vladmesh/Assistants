"""CRUD operations for BatchJob model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.batch_job import BatchJob


async def get(db: AsyncSession, id: UUID) -> BatchJob | None:
    """Get batch job by ID."""
    result = await db.execute(select(BatchJob).where(BatchJob.id == id))
    return result.scalar_one_or_none()


async def get_by_batch_id(db: AsyncSession, batch_id: str) -> BatchJob | None:
    """Get batch job by provider batch_id."""
    result = await db.execute(select(BatchJob).where(BatchJob.batch_id == batch_id))
    return result.scalar_one_or_none()


async def get_pending(
    db: AsyncSession,
    job_type: str = "memory_extraction",
    limit: int = 100,
) -> list[BatchJob]:
    """Get all pending batch jobs."""
    query = (
        select(BatchJob)
        .where(BatchJob.status == "pending")
        .where(BatchJob.job_type == job_type)
        .order_by(BatchJob.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_by_user(
    db: AsyncSession,
    user_id: int,
    status: str | None = None,
    limit: int = 100,
) -> list[BatchJob]:
    """Get batch jobs for a specific user."""
    query = select(BatchJob).where(BatchJob.user_id == user_id)
    if status:
        query = query.where(BatchJob.status == status)
    query = query.order_by(BatchJob.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def create(
    db: AsyncSession,
    *,
    batch_id: str,
    user_id: int,
    assistant_id: UUID | None = None,
    job_type: str = "memory_extraction",
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    messages_processed: int = 0,
    since_timestamp: datetime | None = None,
    until_timestamp: datetime | None = None,
) -> BatchJob:
    """Create a new batch job record."""
    db_obj = BatchJob(
        batch_id=batch_id,
        user_id=user_id,
        assistant_id=assistant_id,
        job_type=job_type,
        provider=provider,
        model=model,
        messages_processed=messages_processed,
        since_timestamp=since_timestamp,
        until_timestamp=until_timestamp,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_status(
    db: AsyncSession,
    *,
    db_obj: BatchJob,
    status: str,
    facts_extracted: int | None = None,
    error_message: str | None = None,
) -> BatchJob:
    """Update batch job status."""
    db_obj.status = status
    if status == "completed":
        db_obj.completed_at = datetime.utcnow()
    if facts_extracted is not None:
        db_obj.facts_extracted = facts_extracted
    if error_message is not None:
        db_obj.error_message = error_message

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete(db: AsyncSession, *, id: UUID) -> BatchJob | None:
    """Delete a batch job."""
    db_obj = await get(db, id=id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        return db_obj
    return None
