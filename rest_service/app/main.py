from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routers import users, tasks, cron_jobs, calendar, assistants
from app.database import init_db
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import logging


# Инициализация приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass

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
app.include_router(tasks.router, prefix="/api", tags=["Tasks"])
app.include_router(cron_jobs.router, prefix="/api", tags=["Cron Jobs"])
app.include_router(calendar.router, prefix="/api", tags=["Calendar"])
app.include_router(assistants.router, prefix="/api", tags=["Assistants"])

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await init_db()

