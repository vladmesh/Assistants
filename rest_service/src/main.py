import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from shared_models import LogEventType, configure_logging, get_logger

from config import settings
from database import init_db
from middleware import CorrelationIdMiddleware

# Import routers from correct locations
from routers import (
    assistant_tools,
    assistants,
    batch_jobs,
    calendar,
    checkpoints,
    conversations,
    global_settings,
    job_executions,
    memory,
    messages,
    queue_stats,
    reminders,
    secretaries,
    tools,
    users,
)

# Configure structured logging
configure_logging(
    service_name="rest_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.LOG_JSON_FORMAT,
)
logger = get_logger(__name__)


# Define a filter to exclude /health endpoint logs
class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if len(record.args) >= 3 and isinstance(record.args[2], str):
                return record.args[2] != "/health"
        except IndexError:
            pass
        return True


# Get the Uvicorn access logger and add the filter
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


# Инициализация приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application lifespan events (startup/shutdown)."""
    logger.info("Starting REST service", event_type=LogEventType.STARTUP)
    await init_db()
    yield
    logger.info("Shutting down REST service", event_type=LogEventType.SHUTDOWN)


app = FastAPI(lifespan=lifespan, title="Assistant Service API")

# Add correlation ID middleware
app.add_middleware(CorrelationIdMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок 422 с логированием."""
    errors = exc.errors()
    logger.error(
        "Validation error",
        event_type=LogEventType.ERROR,
        errors=errors,
        path=str(request.url.path),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


# Подключение роутеров
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(calendar.router, prefix="/api", tags=["Calendar"])
app.include_router(assistants.router, prefix="/api", tags=["Assistants"])
app.include_router(tools.router, prefix="/api", tags=["Tools"])
app.include_router(assistant_tools.router, prefix="/api", tags=["Assistant Tools"])
app.include_router(secretaries.router, prefix="/api", tags=["Secretaries"])
app.include_router(reminders.router, prefix="/api", tags=["Reminders"])
app.include_router(messages.router, prefix="/api", tags=["Messages"])
app.include_router(global_settings.router, prefix="/api", tags=["Global Settings"])
app.include_router(checkpoints.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(batch_jobs.router, prefix="/api")
app.include_router(job_executions.router, prefix="/api")
app.include_router(queue_stats.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
