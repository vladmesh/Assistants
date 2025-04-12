import logging
from contextlib import asynccontextmanager

from api.endpoints import checkpoints  # Import checkpoints separately
from database import init_db
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Import routers from correct locations
from routers import assistant_tools  # Assuming this is also in routers
from routers import secretaries  # Assuming this is also in routers
from routers import (  # user_secretary_links, # Removed non-existent router
    assistants,
    calendar,
    reminders,
    tools,
    users,
)


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
# app.include_router(user_secretary_links.router, prefix="/api") # Removed non-existent router
app.include_router(checkpoints.router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
