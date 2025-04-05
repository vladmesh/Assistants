from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException

from src.models.rag_models import RagData, SearchQuery, SearchResult
from src.services.vector_db_service import VectorDBService

router = APIRouter()


async def get_vector_db_service() -> VectorDBService:
    """Зависимость для получения VectorDBService."""
    return VectorDBService()


@router.get("/health", response_model=Dict[str, str])
async def health_check():
    """Эндпоинт для проверки работоспособности сервиса."""
    return {"status": "ok"}


@router.post("/data/add", response_model=RagData)
async def add_data_endpoint(
    rag_data: RagData,
    vector_db_service: VectorDBService = Depends(get_vector_db_service),
):
    """Эндпоинт для добавления данных в векторную базу данных."""
    try:
        await vector_db_service.add_data(rag_data)
        return rag_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/data/search", response_model=List[SearchResult])
async def search_data_endpoint(
    search_query: SearchQuery,
    vector_db_service: VectorDBService = Depends(get_vector_db_service),
):
    """Эндпоинт для поиска данных в векторной базе данных."""
    try:
        results = await vector_db_service.search_data(
            query_embedding=search_query.query_embedding,
            data_type=search_query.data_type,
            user_id=search_query.user_id,
            assistant_id=search_query.assistant_id,
            top_k=search_query.top_k,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
