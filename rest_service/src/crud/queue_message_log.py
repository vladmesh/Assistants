"""CRUD operations for QueueMessageLog model."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.queue_message_log import QueueDirection, QueueMessageLog


async def get(db: AsyncSession, id: UUID) -> QueueMessageLog | None:
    """Get queue message log by ID."""
    result = await db.execute(select(QueueMessageLog).where(QueueMessageLog.id == id))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    *,
    queue_name: str,
    direction: QueueDirection,
    message_type: str,
    payload: str,
    correlation_id: str | None = None,
    user_id: int | None = None,
    source: str | None = None,
) -> QueueMessageLog:
    """Create a new queue message log entry."""
    db_obj = QueueMessageLog(
        queue_name=queue_name,
        direction=direction,
        message_type=message_type,
        payload=payload,
        correlation_id=correlation_id,
        user_id=user_id,
        source=source,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def mark_processed(db: AsyncSession, id: UUID) -> QueueMessageLog | None:
    """Mark message as processed."""
    db_obj = await get(db, id)
    if db_obj:
        db_obj.processed = True
        db_obj.processed_at = datetime.now(UTC)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
    return db_obj


async def get_list(
    db: AsyncSession,
    *,
    queue_name: str | None = None,
    direction: QueueDirection | None = None,
    user_id: int | None = None,
    correlation_id: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[QueueMessageLog]:
    """Get queue message logs with filters."""
    query = select(QueueMessageLog)

    if queue_name:
        query = query.where(QueueMessageLog.queue_name == queue_name)
    if direction:
        query = query.where(QueueMessageLog.direction == direction)
    if user_id:
        query = query.where(QueueMessageLog.user_id == user_id)
    if correlation_id:
        query = query.where(QueueMessageLog.correlation_id == correlation_id)
    if since:
        query = query.where(QueueMessageLog.created_at >= since)

    query = (
        query.order_by(QueueMessageLog.created_at.desc()).offset(offset).limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_stats(db: AsyncSession, hours: int = 24) -> list[dict]:
    """Get queue statistics for the last N hours."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    hour_ago = datetime.now(UTC) - timedelta(hours=1)

    stats = []
    for queue_name in ["to_secretary", "to_telegram"]:
        # Total messages
        total_query = select(func.count()).where(
            QueueMessageLog.queue_name == queue_name
        )
        total_result = await db.execute(total_query)
        total = total_result.scalar() or 0

        # Last hour
        hour_query = select(func.count()).where(
            QueueMessageLog.queue_name == queue_name,
            QueueMessageLog.created_at >= hour_ago,
        )
        hour_result = await db.execute(hour_query)
        last_hour = hour_result.scalar() or 0

        # Last 24h
        day_query = select(func.count()).where(
            QueueMessageLog.queue_name == queue_name,
            QueueMessageLog.created_at >= since,
        )
        day_result = await db.execute(day_query)
        last_24h = day_result.scalar() or 0

        # By message type (last 24h)
        type_query = (
            select(QueueMessageLog.message_type, func.count())
            .where(
                QueueMessageLog.queue_name == queue_name,
                QueueMessageLog.created_at >= since,
            )
            .group_by(QueueMessageLog.message_type)
        )
        type_result = await db.execute(type_query)
        by_type = {t: c for t, c in type_result.all()}

        # By source (last 24h)
        source_query = (
            select(QueueMessageLog.source, func.count())
            .where(
                QueueMessageLog.queue_name == queue_name,
                QueueMessageLog.created_at >= since,
            )
            .group_by(QueueMessageLog.source)
        )
        source_result = await db.execute(source_query)
        by_source = {s or "unknown": c for s, c in source_result.all()}

        stats.append(
            {
                "queue_name": queue_name,
                "total_messages": total,
                "messages_last_hour": last_hour,
                "messages_last_24h": last_24h,
                "by_type": by_type,
                "by_source": by_source,
            }
        )

    return stats


async def cleanup_old(db: AsyncSession, days: int = 7) -> int:
    """Delete queue message logs older than N days."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    query = select(QueueMessageLog).where(QueueMessageLog.created_at < cutoff)
    result = await db.execute(query)
    logs = list(result.scalars().all())

    count = len(logs)
    for log in logs:
        await db.delete(log)
    await db.commit()
    return count
