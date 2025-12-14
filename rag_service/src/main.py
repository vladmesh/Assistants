from contextlib import asynccontextmanager

from fastapi import FastAPI
from shared_models import LogEventType, configure_logging, get_logger

from api.memory_routes import router as memory_router
from api.routes import router
from config.settings import settings

# Configure logging
configure_logging(
    service_name="rag_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RAG service", event_type=LogEventType.STARTUP)
    yield
    logger.info("Shutting down RAG service", event_type=LogEventType.SHUTDOWN)


app = FastAPI(
    title="RAG Service",
    description="Service for Retrieval-Augmented Generation",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api", tags=["RAG Data"])
app.include_router(memory_router, prefix="/api", tags=["Memory"])


@app.get("/health")
async def health_check():
    """Эндпоинт проверки работоспособности."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)
