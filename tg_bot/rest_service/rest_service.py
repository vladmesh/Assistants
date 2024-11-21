from typing import List, Optional
import requests
from rest_service.models import Task, TelegramUser


class RestService:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def create_task(self, user_id: int, text: str) -> Task:
        """Создать новую задачу."""
        response = requests.post(
            f"{self.base_url}/tasks",
            json={"user_id": user_id, "text": text},
        )
        response.raise_for_status()
        return Task(**response.json())

    def get_tasks(self, user_id: int) -> List[Task]:
        """Получить список задач пользователя."""
        response = requests.get(
            f"{self.base_url}/tasks",
            params={"user_id": user_id},
        )
        response.raise_for_status()
        tasks = response.json()
        return [Task(**task_data) for task_data in tasks]

    def update_task(self, task_id: int, task: Task) -> Task:
        """Обновить задачу."""
        update_data = task.update_dict()  # Используем метод модели для получения полей
        response = requests.patch(
            f"{self.base_url}/tasks/{task_id}",
            json=update_data,
        )
        response.raise_for_status()
        return Task(**response.json())

    def get_or_create_user(self, telegram_id: str, username: Optional[str] = None) -> TelegramUser:
        """Получить или создать пользователя."""
        # Попытка получить пользователя
        response = requests.get(f"{self.base_url}/users", params={"telegram_id": telegram_id})
        if response.status_code == 404:  # Пользователь не найден
            # Создать нового пользователя
            response = requests.post(
                f"{self.base_url}/users",
                json={"telegram_id": telegram_id, "username": username},
            )
            response.raise_for_status()
        elif response.status_code != 200:
            response.raise_for_status()  # Другие ошибки

        return TelegramUser(**response.json())