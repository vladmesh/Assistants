from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routers import users, tasks
from app.database import init_db
from fastapi.exceptions import RequestValidationError
import logging


# Инициализация приложения
app = FastAPI()
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


# Создание таблиц при старте сервиса
@app.on_event("startup")
def on_startup():
    init_db(True)
