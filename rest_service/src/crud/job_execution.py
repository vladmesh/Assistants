"""CRUD operations for JobExecution model."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.job_execution import JobExecution, JobStatus


async def get(db: AsyncSession, id: UUID) -> JobExecution | None:
    """Get job execution by ID."""
    result = await db.execute(select(JobExecution).where(JobExecution.id == id))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    job_id: str,
    job_name: str,
    job_type: str,
    scheduled_at: datetime,
    user_id: int | None = None,
    reminder_id: int | None = None,
) -> JobExecution:
    """Create a new job execution record."""
    db_obj = JobExecution(
        job_id=job_id,
        job_name=job_name,
        job_type=job_type,
        scheduled_at=scheduled_at,
        user_id=user_id,
        reminder_id=reminder_id,
        status=JobStatus.SCHEDULED,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def start(db: AsyncSession, id: UUID) -> JobExecution | None:
    """Mark job as started."""
    db_obj = await get(db, id)
    if db_obj:
        db_obj.status = JobStatus.RUNNING
        db_obj.started_at = datetime.now(UTC)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
    return db_obj


async def complete(
    db: AsyncSession,
    id: UUID,
    result: str | None = None,
) -> JobExecution | None:
    """Mark job as completed."""
    db_obj = await get(db, id)
    if db_obj:
        db_obj.status = JobStatus.COMPLETED
        db_obj.finished_at = datetime.now(UTC)
        if db_obj.started_at:
            delta = db_obj.finished_at - db_obj.started_at
            db_obj.duration_ms = int(delta.total_seconds() * 1000)
        db_obj.result = result
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
    return db_obj


async def fail(
    db: AsyncSession,
    id: UUID,
    error: str,
    error_traceback: str | None = None,
) -> JobExecution | None:
    """Mark job as failed."""
    db_obj = await get(db, id)
    if db_obj:
        db_obj.status = JobStatus.FAILED
        db_obj.finished_at = datetime.now(UTC)
        if db_obj.started_at:
            delta = db_obj.finished_at - db_obj.started_at
            db_obj.duration_ms = int(delta.total_seconds() * 1000)
        db_obj.error = error
        db_obj.error_traceback = error_traceback
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
    return db_obj


async def get_list(
    db: AsyncSession,
    *,
    job_type: str | None = None,
    status: JobStatus | None = None,
    user_id: int | None = None,
    since: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[JobExecution]:
    """Get job executions with filters."""
    query = select(JobExecution)

    if job_type:
        query = query.where(JobExecution.job_type == job_type)
    if status:
        query = query.where(JobExecution.status == status)
    if user_id:
        query = query.where(JobExecution.user_id == user_id)
    if since:
        query = query.where(JobExecution.created_at >= since)

    query = query.order_by(JobExecution.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_stats(db: AsyncSession, hours: int = 24) -> dict:
    """Get job execution statistics for the last N hours."""
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Get all jobs in period
    query = select(JobExecution).where(JobExecution.created_at >= since)
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    stats = {
        "total": len(jobs),
        "completed": sum(1 for j in jobs if j.status == JobStatus.COMPLETED),
        "failed": sum(1 for j in jobs if j.status == JobStatus.FAILED),
        "running": sum(1 for j in jobs if j.status == JobStatus.RUNNING),
        "scheduled": sum(1 for j in jobs if j.status == JobStatus.SCHEDULED),
        "avg_duration_ms": 0,
        "by_type": {},
    }

    durations = [j.duration_ms for j in jobs if j.duration_ms]
    if durations:
        stats["avg_duration_ms"] = sum(durations) // len(durations)

    for job in jobs:
        if job.job_type not in stats["by_type"]:
            stats["by_type"][job.job_type] = {"total": 0, "failed": 0}
        stats["by_type"][job.job_type]["total"] += 1
        if job.status == JobStatus.FAILED:
            stats["by_type"][job.job_type]["failed"] += 1

    return stats


async def cleanup_old(db: AsyncSession, days: int = 7) -> int:
    """Delete job executions older than N days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    query = select(JobExecution).where(JobExecution.created_at < cutoff)
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    count = len(jobs)
    for job in jobs:
        await db.delete(job)
    await db.commit()
    return count
