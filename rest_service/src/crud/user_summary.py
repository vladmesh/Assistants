from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from models.user_summary import UserSummary
from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared_models.api_schemas import UserSummaryCreateUpdate


async def get_summary_by_id(db: AsyncSession, id: int) -> Optional[UserSummary]:
    result = await db.execute(select(UserSummary).where(UserSummary.id == id))
    return result.scalar_one_or_none()


async def get_latest_by_user_and_assistant(
    db: AsyncSession, *, user_id: int, assistant_id: UUID
) -> Optional[UserSummary]:
    statement = (
        select(UserSummary)
        .where(UserSummary.user_id == user_id, UserSummary.assistant_id == assistant_id)
        .order_by(desc(UserSummary.id))
        .limit(1)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_multi_summaries(
    db: AsyncSession,
    *,
    user_id: Optional[int] = None,
    assistant_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "id",
    sort_order: str = "desc",
) -> List[UserSummary]:
    query = select(UserSummary)
    if user_id is not None:
        query = query.where(UserSummary.user_id == user_id)
    if assistant_id is not None:
        query = query.where(UserSummary.assistant_id == assistant_id)

    sort_column = getattr(UserSummary, sort_by, UserSummary.id)

    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_summary(
    db: AsyncSession, *, obj_in: UserSummaryCreateUpdate
) -> UserSummary:
    db_obj = UserSummary.model_validate(obj_in)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update_summary(
    db: AsyncSession,
    *,
    db_obj: UserSummary,
    obj_in: Union[UserSummaryCreateUpdate, Dict[str, Any]],
) -> UserSummary:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj
