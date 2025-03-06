import pytest
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from app.models import *
from app.main import app
from app.database import engine as main_engine, get_session
from fastapi.testclient import TestClient

# Создаем отдельный engine для тестов
TEST_DATABASE_URL = "postgresql://test_user:test_password@localhost:5433/test_db"
test_engine = create_engine(TEST_DATABASE_URL, echo=True)

@pytest.fixture(scope="session")
def test_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)

@pytest.fixture
def db_session(test_db):
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    # Очищаем все таблицы перед каждым тестом
    for table in reversed(SQLModel.metadata.sorted_tables):
        session.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
    session.commit()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    # Подменяем engine в основном приложении на тестовый
    app.dependency_overrides = {}
    app.dependency_overrides[get_session] = lambda: db_session
    return TestClient(app)

@pytest.fixture
def test_user(db_session):
    user = TelegramUser(
        telegram_id=123456789,
        username="test_user"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user 