import logging
from contextlib import asynccontextmanager

from database import init_db
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Import routers from correct locations
# from api.endpoints import checkpoints # Import checkpoints separately
from routers import assistant_tools  # Assuming this is also in routers
from routers import checkpoints  # Import checkpoints from routers
from routers import messages  # Добавлен импорт messages
from routers import secretaries  # Assuming this is also in routers
from routers import user_facts  # Add user_facts
from routers import (  # user_secretary_links, # Removed non-existent router
    assistants,
    calendar,
    global_settings,
    reminders,
    tools,
    user_summaries,
    users,
)


# Define a filter to exclude /health endpoint logs
class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn access logs typically have scope info in args
        # Check if the path in the access log record is /health
        # Example format: ('127.0.0.1:12345', 'GET', '/health', '1.1', 200)
        # Note: Args positions might vary based on Uvicorn version/config
        try:
            if len(record.args) >= 3 and isinstance(record.args[2], str):
                return record.args[2] != "/health"
        except IndexError:
            pass  # Or log a warning if needed
        return True


# Get the Uvicorn access logger and add the filter
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
# --- End Logging Configuration ---


# Инициализация приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application lifespan events (startup/shutdown)."""
    # Startup
    await init_db()
    yield
    # Shutdown


app = FastAPI(lifespan=lifespan, title="Assistant Service API")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обработчик ошибок 422 с логированием."""
    errors = exc.errors()
    logger.error(f"Ошибка валидации: {errors}")
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
app.include_router(
    user_facts.router, prefix="/api", tags=["User Facts"]
)  # Add user_facts router
app.include_router(user_summaries.router, prefix="/api", tags=["User Summaries"])
app.include_router(
    messages.router, prefix="/api", tags=["Messages"]
)  # Добавлен префикс "/api"
app.include_router(global_settings.router, prefix="/api", tags=["Global Settings"])
app.include_router(checkpoints.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
