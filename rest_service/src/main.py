import logging
from contextlib import asynccontextmanager

from database import init_db
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from routers import (
    assistant_tools,
    assistants,
    calendar,
    reminders,
    secretaries,
    tools,
    users,
)


# Инициализация приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
