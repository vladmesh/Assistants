"""Task fixtures"""
import random
from app.models import Task, TaskStatus, TelegramUser

def create_test_tasks(users: list[TelegramUser]) -> list[Task]:
    """Create test tasks fixtures"""
    return [
        Task(
            title="Test Task 1",
            description="Description for task 1",
            status=random.choice(list(TaskStatus)),
            user=users[0]
        ),
        Task(
            title="Test Task 2",
            description="Description for task 2",
            status=random.choice(list(TaskStatus)),
            user=users[1]
        )
    ] 