from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from shared_models import MemoryCreate, MemoryRead, MemoryUpdate
from sqlmodel import Session, select

from database import get_session
from models import Memory

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post("/", response_model=MemoryRead)
async def create_memory(
    memory_in: MemoryCreate,
    session: Annotated[Session, Depends(get_session)],
):
    memory = Memory.model_validate(memory_in)
    session.add(memory)
    session.commit()
    session.refresh(memory)
    return memory


@router.get("/{memory_id}", response_model=MemoryRead)
async def get_memory(
    memory_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    memory = session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.patch("/{memory_id}", response_model=MemoryRead)
async def update_memory(
    memory_id: UUID,
    memory_update: MemoryUpdate,
    session: Annotated[Session, Depends(get_session)],
):
    db_memory = session.get(Memory, memory_id)
    if not db_memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory_data = memory_update.model_dump(exclude_unset=True)
    for key, value in memory_data.items():
        setattr(db_memory, key, value)

    session.add(db_memory)
    session.commit()
    session.refresh(db_memory)
    return db_memory


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    session: Annotated[Session, Depends(get_session)],
):
    memory = session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    session.delete(memory)
    session.commit()
    return {"ok": True}


@router.get("/user/{user_id}", response_model=list[MemoryRead])
async def get_user_memories(
    user_id: int,
    session: Annotated[Session, Depends(get_session)],
    limit: int = 100,
    offset: int = 0,
):
    statement = (
        select(Memory).where(Memory.user_id == user_id).offset(offset).limit(limit)
    )
    return session.exec(statement).all()


@router.post("/search", response_model=list[MemoryRead])
async def search_memories(
    embedding: list[float],
    user_id: int,
    session: Annotated[Session, Depends(get_session)],
    limit: int = 10,
    threshold: float = 0.7,
):
    statement = (
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.embedding.cosine_distance(embedding))
        .limit(limit)
    )
    # TODO: Add threshold filtering if needed, but cosine distance is 0..2
    # (0=identical, 1=orthogonal, 2=opposite)
    # For now just return top K
    return session.exec(statement).all()
