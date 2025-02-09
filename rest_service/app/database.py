from sqlmodel import SQLModel, create_engine, Session
from .models import TelegramUser, Task, CronJob, TaskStatus, CronJobType
import os
import random
from sqlalchemy import text

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
        with engine.begin() as conn:
            # Удаляем public со всеми таблицами, последовательностями и т.д.
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    SQLModel.metadata.create_all(engine)  # Создаём таблицы




def create_test_data():
    """
    Создаёт тестовые данные для базы данных.
    """
    with Session(engine) as session:
        # Проверяем, есть ли уже данные, чтобы не создавать дубликаты
        if session.query(TelegramUser).first():
            print("Тестовые данные уже существуют. Пропускаем.")
            return

        # Создаём тестовых пользователей
        user1 = TelegramUser(telegram_id=625038902, username="vladmesh")
        user2 = TelegramUser(telegram_id=7192117299, username="vladislav_meshk")

        # Создаём тестовые задачи
        task1 = Task(
            title="Test Task 1",
            description="Description for task 1",
            status=random.choice(list(TaskStatus)),
            user=user1
        )
        task2 = Task(
            title="Test Task 2",
            description="Description for task 2",
            status=random.choice(list(TaskStatus)),
            user=user2
        )

        # Создаём тестовые CronJob
        job1 = CronJob(
            name="Test Job 1",
            type=CronJobType.NOTIFICATION,
            cron_expression="9 * * * *",
            user=user1
        )
        job2 = CronJob(
            name="Test Job 2",
            type=CronJobType.SCHEDULE,
            cron_expression="0 12 * * *",
            user=user2
        )

        # Сохраняем в базу
        session.add_all([user1, user2, task1, task2, job1, job2])
        session.commit()
        print("Тестовые данные успешно созданы.")
