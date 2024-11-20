from fastapi import FastAPI
from app.routers import users, tasks
from app.database import init_db

# Инициализация приложения
app = FastAPI()

# Подключение роутеров
app.include_router(users.router, prefix="/api", tags=["Users"])
app.include_router(tasks.router, prefix="/api", tags=["Tasks"])

# Создание таблиц при старте сервиса
@app.on_event("startup")
def on_startup():
    init_db()
