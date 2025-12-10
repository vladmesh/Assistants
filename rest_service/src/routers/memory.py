from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from shared_models import MemoryCreate, MemoryRead, MemoryUpdate
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import Memory

router = APIRouter(prefix="/memories", tags=["memories"])


class MemorySearchRequest(BaseModel):
    """Request body for memory search endpoint."""

    embedding: list[float] = Field(..., description="Query embedding vector")
    user_id: int = Field(..., description="User ID to filter memories")
    limit: int = Field(default=10, ge=1, le=100, description="Max results to return")
    threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Similarity threshold"
    )


@router.post("/", response_model=MemoryRead)
async def create_memory(
    memory_in: MemoryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    memory = Memory.model_validate(memory_in)
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory


@router.get("/{memory_id}", response_model=MemoryRead)
async def get_memory(
    memory_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    memory = await session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


@router.patch("/{memory_id}", response_model=MemoryRead)
async def update_memory(
    memory_id: UUID,
    memory_update: MemoryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    db_memory = await session.get(Memory, memory_id)
    if not db_memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory_data = memory_update.model_dump(exclude_unset=True)
    for key, value in memory_data.items():
        setattr(db_memory, key, value)

    session.add(db_memory)
    await session.commit()
    await session.refresh(db_memory)
    return db_memory


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    memory = await session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    await session.delete(memory)
    await session.commit()
    return {"ok": True}


@router.get("/user/{user_id}", response_model=list[MemoryRead])
async def get_user_memories(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 100,
    offset: int = 0,
):
    statement = (
        select(Memory).where(Memory.user_id == user_id).offset(offset).limit(limit)
    )
    result = await session.exec(statement)
    return result.all()


class MemorySearchResponse(MemoryRead):
    """Memory with similarity score for search results."""

    score: float = Field(..., description="Similarity score (0-1, higher is better)")


@router.post("/search", response_model=list[MemorySearchResponse])
async def search_memories(
    request: MemorySearchRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Search memories by embedding similarity.

    Returns memories ordered by cosine similarity, filtered by threshold.
    Score is calculated as 1 - cosine_distance (so 1 = identical, 0 = orthogonal).
    """
    statement = (
        select(
            Memory,
            (1 - Memory.embedding.cosine_distance(request.embedding)).label("score"),
        )
        .where(Memory.user_id == request.user_id)
        .where(Memory.embedding.isnot(None))
        .order_by(Memory.embedding.cosine_distance(request.embedding))
        .limit(request.limit)
    )

    result = await session.exec(statement)
    results = result.all()

    # Filter by threshold and convert to response model
    response = []
    for memory, score in results:
        if score >= request.threshold:
            memory_dict = memory.model_dump()
            memory_dict["score"] = round(score, 4)
            response.append(MemorySearchResponse(**memory_dict))

    return response
