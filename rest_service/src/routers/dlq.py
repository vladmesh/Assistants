"""Dead Letter Queue (DLQ) management API routes."""

from datetime import UTC, datetime
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from models.dlq import DLQMessageResponse, DLQStatsResponse

router = APIRouter(prefix="/dlq", tags=["dlq"])


async def get_redis(request: Request) -> redis.Redis:
    """Get Redis client from app state."""
    redis_client = getattr(request.app.state, "redis_client", None)
    if not redis_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis not available",
        )
    return redis_client


@router.get("/messages", response_model=list[DLQMessageResponse])
async def list_dlq_messages(
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: Annotated[str, Query(description="Queue name")] = "to_secretary",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    error_type: Annotated[str | None, Query(description="Filter by error type")] = None,
    user_id: Annotated[str | None, Query(description="Filter by user ID")] = None,
) -> list[DLQMessageResponse]:
    """List messages in DLQ with optional filters."""
    dlq_stream = f"{queue}:dlq"

    entries = await redis_client.xrange(dlq_stream, count=limit * 2)

    messages = []
    for msg_id, fields in entries:
        failed_at_str = fields.get("failed_at")
        try:
            failed_at = (
                datetime.fromisoformat(failed_at_str)
                if failed_at_str
                else datetime.now(UTC)
            )
        except ValueError:
            failed_at = datetime.now(UTC)

        msg = DLQMessageResponse(
            message_id=msg_id,
            original_message_id=fields.get("original_message_id", ""),
            payload=fields.get("payload", ""),
            error_type=fields.get("error_type", "unknown"),
            error_message=fields.get("error_message", ""),
            retry_count=int(fields.get("retry_count", 0)),
            failed_at=failed_at,
            user_id=fields.get("user_id") or None,
        )

        if error_type and msg.error_type != error_type:
            continue
        if user_id and msg.user_id != user_id:
            continue

        messages.append(msg)
        if len(messages) >= limit:
            break

    return messages


@router.get("/stats", response_model=DLQStatsResponse)
async def get_dlq_stats(
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: Annotated[str, Query(description="Queue name")] = "to_secretary",
) -> DLQStatsResponse:
    """Get DLQ statistics."""
    dlq_stream = f"{queue}:dlq"

    total = await redis_client.xlen(dlq_stream)

    entries = await redis_client.xrange(dlq_stream, count=1000)

    by_error_type: dict[str, int] = {}
    oldest: datetime | None = None
    newest: datetime | None = None

    for _, fields in entries:
        err_type = fields.get("error_type", "unknown")
        by_error_type[err_type] = by_error_type.get(err_type, 0) + 1

        failed_at_str = fields.get("failed_at")
        if failed_at_str:
            try:
                failed_at = datetime.fromisoformat(failed_at_str)
                if oldest is None or failed_at < oldest:
                    oldest = failed_at
                if newest is None or failed_at > newest:
                    newest = failed_at
            except ValueError:
                pass

    return DLQStatsResponse(
        queue_name=queue,
        total_messages=total,
        by_error_type=by_error_type,
        oldest_message_at=oldest,
        newest_message_at=newest,
    )


@router.post("/messages/{message_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_dlq_message(
    message_id: str,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: Annotated[str, Query(description="Queue name")] = "to_secretary",
) -> dict:
    """Retry a message from DLQ - move back to main queue."""
    dlq_stream = f"{queue}:dlq"

    entries = await redis_client.xrange(
        dlq_stream, min=message_id, max=message_id, count=1
    )
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in DLQ",
        )

    _, fields = entries[0]
    payload = fields.get("payload", "")

    new_id = await redis_client.xadd(queue, {"payload": payload})

    await redis_client.xdel(dlq_stream, message_id)

    return {
        "status": "requeued",
        "original_dlq_message_id": message_id,
        "new_message_id": new_id,
    }


@router.delete("/messages/{message_id}", status_code=status.HTTP_200_OK)
async def delete_dlq_message(
    message_id: str,
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: Annotated[str, Query(description="Queue name")] = "to_secretary",
) -> dict:
    """Delete a message from DLQ (after manual review)."""
    dlq_stream = f"{queue}:dlq"

    deleted = await redis_client.xdel(dlq_stream, message_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found in DLQ",
        )

    return {"status": "deleted", "message_id": message_id}


@router.delete("/messages", status_code=status.HTTP_200_OK)
async def purge_dlq(
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    queue: Annotated[str, Query(description="Queue name")] = "to_secretary",
    error_type: Annotated[
        str | None, Query(description="Filter by error type (optional)")
    ] = None,
) -> dict:
    """Purge all messages from DLQ (optionally filtered by error_type)."""
    dlq_stream = f"{queue}:dlq"

    if error_type:
        entries = await redis_client.xrange(dlq_stream)
        deleted_count = 0
        for msg_id, fields in entries:
            if fields.get("error_type") == error_type:
                await redis_client.xdel(dlq_stream, msg_id)
                deleted_count += 1
        return {
            "status": "purged",
            "deleted_count": deleted_count,
            "filter": error_type,
        }
    else:
        await redis_client.delete(dlq_stream)
        return {"status": "purged", "queue": dlq_stream}
