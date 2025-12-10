"""Conversations API for memory extraction.

Provides endpoints to retrieve conversations grouped by user/assistant
for batch fact extraction.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models.message import Message

logger = structlog.get_logger()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationMessage(BaseModel):
    """Single message in a conversation."""

    id: int
    role: str
    content: str
    timestamp: datetime


class Conversation(BaseModel):
    """Grouped conversation for a user/assistant pair."""

    user_id: int
    assistant_id: UUID
    messages: list[ConversationMessage]
    message_count: int
    earliest_timestamp: datetime
    latest_timestamp: datetime


class ConversationsResponse(BaseModel):
    """Response containing list of conversations."""

    conversations: list[Conversation]
    total_conversations: int
    total_messages: int


@router.get("/", response_model=ConversationsResponse)
async def get_conversations(
    session: SessionDep,
    since: Annotated[
        datetime | None,
        Query(description="Filter messages since this timestamp (ISO 8601)"),
    ] = None,
    user_id: Annotated[
        int | None,
        Query(description="Filter by specific user ID"),
    ] = None,
    assistant_id: Annotated[
        UUID | None,
        Query(description="Filter by specific assistant ID"),
    ] = None,
    min_messages: Annotated[
        int,
        Query(description="Minimum messages per conversation to include"),
    ] = 2,
    limit: Annotated[
        int,
        Query(le=100, description="Maximum number of conversations to return"),
    ] = 50,
) -> ConversationsResponse:
    """
    Get conversations grouped by user_id and assistant_id.

    Used by memory extraction job to fetch recent dialogs for fact extraction.
    Returns conversations with at least `min_messages` messages.

    Args:
        since: Only include messages after this timestamp
        user_id: Filter to specific user
        assistant_id: Filter to specific assistant
        min_messages: Minimum messages per conversation (default: 2)
        limit: Maximum conversations to return (default: 50)
    """
    logger.info(
        "Fetching conversations",
        since=since,
        user_id=user_id,
        assistant_id=assistant_id,
        min_messages=min_messages,
    )

    # Build query for messages
    query = select(Message).where(Message.status == "active")

    if since is not None:
        query = query.where(Message.timestamp >= since)
    if user_id is not None:
        query = query.where(Message.user_id == user_id)
    if assistant_id is not None:
        query = query.where(Message.assistant_id == assistant_id)

    # Order by user, assistant, timestamp for grouping
    query = query.order_by(
        Message.user_id, Message.assistant_id, Message.timestamp.asc()
    )

    result = await session.execute(query)
    messages = result.scalars().all()

    # Group messages by (user_id, assistant_id)
    conversations_dict: dict[tuple[int, UUID], list[Message]] = {}
    for msg in messages:
        key = (msg.user_id, msg.assistant_id)
        if key not in conversations_dict:
            conversations_dict[key] = []
        conversations_dict[key].append(msg)

    # Build response, filtering by min_messages
    conversations: list[Conversation] = []
    total_messages = 0

    for (uid, aid), msgs in conversations_dict.items():
        if len(msgs) < min_messages:
            continue

        conv_messages = [
            ConversationMessage(
                id=m.id,
                role=m.role,
                content=m.content,
                timestamp=m.timestamp,
            )
            for m in msgs
        ]

        conversations.append(
            Conversation(
                user_id=uid,
                assistant_id=aid,
                messages=conv_messages,
                message_count=len(conv_messages),
                earliest_timestamp=msgs[0].timestamp,
                latest_timestamp=msgs[-1].timestamp,
            )
        )
        total_messages += len(conv_messages)

        if len(conversations) >= limit:
            break

    logger.info(
        "Conversations fetched",
        total_conversations=len(conversations),
        total_messages=total_messages,
    )

    return ConversationsResponse(
        conversations=conversations,
        total_conversations=len(conversations),
        total_messages=total_messages,
    )
