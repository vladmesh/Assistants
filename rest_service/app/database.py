from sqlmodel import SQLModel, create_engine, Session
import os

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session

def init_db(reset: bool = False):
    """
    Инициализация базы данных.
    Если reset=True, база данных пересоздаётся.
    """
    if reset:
        SQLModel.metadata.drop_all(engine)  # Удаляем все таблицы
    SQLModel.metadata.create_all(engine)  # Создаём таблицы
