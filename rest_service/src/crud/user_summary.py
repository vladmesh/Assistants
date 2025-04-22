from typing import Optional
from uuid import UUID

from models.user_summary import UserSummary
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_summary(
    db: AsyncSession, user_id: int, secretary_id: UUID
) -> Optional[UserSummary]:
    """Retrieve the *latest* summary for a given user and secretary.

    Args:
        db: The async database session.
        user_id: The ID of the user.
        secretary_id: The ID of the secretary assistant.

    Returns:
        The latest UserSummary object if found, otherwise None.
    """
    statement = (
        select(UserSummary)
        .where(UserSummary.user_id == user_id, UserSummary.secretary_id == secretary_id)
        .order_by(desc(UserSummary.created_at))
        .limit(1)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def create_or_update_summary(
    db: AsyncSession, user_id: int, secretary_id: UUID, summary_text: str
) -> UserSummary:
    """Create a *new* summary entry for a user and secretary.
    This function now always creates a new record to maintain history.

    Args:
        db: The async database session.
        user_id: The ID of the user.
        secretary_id: The ID of the secretary assistant.
        summary_text: The text content of the summary.

    Returns:
        The newly created UserSummary object.
    """
    # Always create a new summary record
    new_summary = UserSummary(
        user_id=user_id,
        secretary_id=secretary_id,
        summary_text=summary_text,
    )
    db.add(new_summary)
    await db.commit()
    await db.refresh(new_summary)
    return new_summary
