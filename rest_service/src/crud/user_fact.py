from typing import Sequence
from uuid import UUID

from models import UserFact
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas.user_fact import UserFactCreate


async def create_user_fact(db: AsyncSession, user_fact_in: UserFactCreate) -> UserFact:
    """Create a new user fact."""
    db_user_fact = UserFact.model_validate(user_fact_in)
    db.add(db_user_fact)
    await db.commit()
    await db.refresh(db_user_fact)
    return db_user_fact


async def get_user_facts_by_user_id(
    db: AsyncSession, user_id: int
) -> Sequence[UserFact]:
    """Get all facts for a specific user."""
    statement = select(UserFact).where(UserFact.user_id == user_id)
    result = await db.exec(statement)
    return result.all()


async def get_user_fact_by_id(db: AsyncSession, fact_id: UUID) -> UserFact | None:
    """Get a user fact by its ID."""
    statement = select(UserFact).where(UserFact.id == fact_id)
    result = await db.exec(statement)
    return result.first()


async def delete_user_fact(db: AsyncSession, db_user_fact: UserFact) -> None:
    """Delete a user fact."""
    await db.delete(db_user_fact)
    await db.commit()
    return None
