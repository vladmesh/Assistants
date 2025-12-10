from fastapi import APIRouter

router = APIRouter()


@router.get("/health", response_model=dict[str, str])
async def health_check():
    """Эндпоинт для проверки работоспособности сервиса."""
    return {"status": "ok"}
