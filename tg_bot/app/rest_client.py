import os
import requests
from typing import Optional, Dict, Any, List


class RestClient:
    """Клиент для работы с REST API."""
    
    def __init__(self):
        self.base_url = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")
        self.api_prefix = "/api"
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Выполняет HTTP-запрос к API."""
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        print(f"Making request to {url}")  # Добавляем логирование
        response = requests.request(method, url, **kwargs)
        print(f"Response status: {response.status_code}")  # Добавляем логирование
        print(f"Response body: {response.text}")  # Добавляем логирование
        response.raise_for_status()
        return response.json()
    
    def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает пользователя по telegram_id."""
        try:
            response = self._make_request(
                "GET",
                "/users/",
                params={"telegram_id": telegram_id}
            )
            # Если API вернул пустой список или словарь без данных
            if not response:
                return None
            # Если API вернул список пользователей
            if isinstance(response, list):
                return response[0] if response else None
            # Если API вернул одного пользователя как словарь
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error in get_user: {e}")
            return None
    
    def create_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Создает нового пользователя."""
        return self._make_request(
            "POST",
            "/users/",
            json={
                "telegram_id": telegram_id,
                "username": username
            }
        )
    
    def get_or_create_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Получает или создает пользователя."""
        try:
            # Пробуем найти пользователя
            user = self.get_user(telegram_id)
            if user:
                return user
            
            # Если пользователь не найден, создаем нового
            return self.create_user(telegram_id, username)
        except requests.exceptions.RequestException as e:
            print(f"Error in get_or_create_user: {e}")
            # В случае ошибки возвращаем базовую информацию о пользователе
            return {
                "id": telegram_id,
                "telegram_id": telegram_id,
                "username": username
            }
    
    def get_user_tasks(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает список задач пользователя."""
        try:
            return self._make_request(
                "GET",
                f"/tasks/active/{user_id}"
            )
        except requests.exceptions.RequestException as e:
            print(f"Error in get_user_tasks: {e}")
            return []
    
    def create_task(self, user_id: int, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Создает новую задачу."""
        return self._make_request(
            "POST",
            "/tasks/",
            json={
                "user_id": user_id,
                "title": name,
                "description": description,
                "status": "Активно"
            }
        )
    
    def update_task_status(self, task_id: int, status: str) -> Dict[str, Any]:
        """Обновляет статус задачи."""
        return self._make_request(
            "PATCH",
            f"/tasks/{task_id}",
            json={"status": status}
        ) 