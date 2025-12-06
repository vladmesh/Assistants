import structlog
from fastapi import FastAPI

from src.api.memory_routes import router as memory_router
from src.api.routes import router
from src.config.settings import settings

logger = structlog.get_logger()

app = FastAPI(
    title="RAG Service",
    description="Service for Retrieval-Augmented Generation",
    version="0.1.0",
)

app.include_router(router, prefix="/api", tags=["RAG Data"])
app.include_router(memory_router, prefix="/api", tags=["Memory"])


@app.on_event("startup")
async def startup_event():
    logger.info("Starting RAG service")


@app.get("/health")
async def health_check():
    """Эндпоинт проверки работоспособности."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)
