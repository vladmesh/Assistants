"""Memory API routes for RAG service."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from src.models.memory_models import (
    MemoryCreateRequest,
    MemorySearchQuery,
)
from src.services.memory_service import MemoryService

router = APIRouter(prefix="/memories", tags=["memories"])


async def get_memory_service() -> MemoryService:
    """Dependency for getting MemoryService."""
    return MemoryService()


@router.post("/search")
async def search_memories_endpoint(
    search_query: MemorySearchQuery,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> list[dict]:
    """Search for relevant memories using text query.

    This endpoint:
    1. Generates embedding for the query
    2. Calls rest_service to search memories
    3. Returns matching memories
    """
    try:
        results = await memory_service.search_memories(
            query=search_query.query,
            user_id=search_query.user_id,
            limit=search_query.limit,
            threshold=search_query.threshold,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/create")
async def create_memory_endpoint(
    memory_request: MemoryCreateRequest,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> dict:
    """Create a new memory with auto-generated embedding.

    This endpoint:
    1. Generates embedding for the text
    2. Calls rest_service to create the memory
    3. Returns the created memory
    """
    try:
        memory = await memory_service.create_memory(
            user_id=memory_request.user_id,
            text=memory_request.text,
            memory_type=memory_request.memory_type,
            assistant_id=memory_request.assistant_id,
            importance=memory_request.importance,
        )
        return memory
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
