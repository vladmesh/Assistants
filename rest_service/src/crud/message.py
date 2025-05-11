from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from models.message import Message
from sqlalchemy import asc, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import MessageCreate, MessageUpdate

# It's good practice to use a base CRUD class if there's common logic,
# but for now, we'll implement functions directly as per the plan's structure for CRUDMessage.


async def get(db: AsyncSession, id: int) -> Optional[Message]:
    result = await db.execute(select(Message).where(Message.id == id))
    return result.scalar_one_or_none()


async def get_multi(
    db: AsyncSession,
    *,
    user_id: Optional[int] = None,
    assistant_id: Optional[UUID] = None,
    id_gt: Optional[int] = None,
    id_lt: Optional[int] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    summary_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "id",
    sort_order: str = "asc",
) -> List[Message]:
    query = select(Message)
    if user_id is not None:
        query = query.where(Message.user_id == user_id)
    if assistant_id is not None:
        query = query.where(Message.assistant_id == assistant_id)
    if id_gt is not None:
        query = query.where(Message.id > id_gt)
    if id_lt is not None:
        query = query.where(Message.id < id_lt)
    if role is not None:
        query = query.where(Message.role == role)
    if status is not None:
        query = query.where(Message.status == status)
    if summary_id is not None:
        query = query.where(Message.summary_id == summary_id)

    sort_column = getattr(Message, sort_by, None)
    if sort_column is None:
        sort_column = Message.id  # Default to id if sort_by is invalid

    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create(db: AsyncSession, *, obj_in: MessageCreate) -> Message:
    # SQLModel uses model_validate for Pydantic v2
    # For older Pydantic v1 style with SQLModel, it's usually:
    # db_obj = Message(**obj_in.dict())
    # or for Pydantic v2 with SQLModel that supports it:
    db_obj = Message.model_validate(obj_in)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def update(
    db: AsyncSession, *, db_obj: Message, obj_in: Union[MessageUpdate, Dict[str, Any]]
) -> Message:
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        # exclude_unset=True ensures only provided fields are used for update
        update_data = obj_in.model_dump(exclude_unset=True)

    print(f"DEBUG - update_data before update: {update_data}")
    print(
        f"DEBUG - db_obj before update: summary_id={db_obj.summary_id}, status={db_obj.status}"
    )

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    print(
        f"DEBUG - db_obj after update: summary_id={db_obj.summary_id}, status={db_obj.status}"
    )

    db.add(db_obj)  # Add to session to track changes
    await db.commit()
    await db.refresh(db_obj)

    print(
        f"DEBUG - db_obj after refresh: summary_id={db_obj.summary_id}, status={db_obj.status}"
    )

    return db_obj


async def remove(db: AsyncSession, *, id: int) -> Optional[Message]:
    db_obj = await get(db, id=id)  # Reuse the get method
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        return db_obj
    return None
