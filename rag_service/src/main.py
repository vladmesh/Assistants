from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from shared_models import LogEventType, configure_logging, get_logger

from api.memory_routes import router as memory_router
from api.routes import router
from config.settings import settings
from metrics import PrometheusMiddleware, get_content_type, get_metrics

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

# Add metrics middleware
app.add_middleware(PrometheusMiddleware)

app.include_router(router, prefix="/api", tags=["RAG Data"])
app.include_router(memory_router, prefix="/api", tags=["Memory"])


@app.get("/health")
async def health_check():
    """Эндпоинт проверки работоспособности."""
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=get_metrics(), media_type=get_content_type())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.API_PORT)
