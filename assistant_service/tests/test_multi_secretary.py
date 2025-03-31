import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Добавляем путь к src в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from assistants.factory import AssistantFactory
from messages.base import HumanMessage


@pytest.mark.external_api
class TestMultiSecretary:
    """Тесты для функционала с несколькими секретарями"""

    def get_last_assistant_message(self, response: dict) -> str:
        """Получает последнее сообщение ассистента из ответа"""
        messages = response.get("messages", [])
        for message in reversed(messages):
            if (
                hasattr(message, "content")
                and isinstance(message.content, str)
                and message.content
            ):
                return message.content
        return ""

    @pytest.fixture
    def mock_rest_client(self):
        """Создает мок для RestServiceClient"""
        with patch("assistants.factory.RestServiceClient") as mock:
            # Создаем мок для метода get_user_secretary
            mock_instance = AsyncMock()
            mock_instance.get_user_secretary.return_value = {
                "id": "test-secretary-id",
                "name": "test_secretary",
                "type": "llm",
                "instructions": "Ты - тестовый секретарь",
            }
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def factory(self, mock_rest_client):
        """Создает экземпляр AssistantFactory с моком RestServiceClient"""
        return AssistantFactory(settings=MagicMock(), rest_client=mock_rest_client)

    @pytest.mark.asyncio
    async def test_get_user_secretary(self, factory, mock_rest_client):
        """
        Тест проверяет:
        1. Получение секретаря для пользователя через REST API
        2. Создание экземпляра секретаря
        3. Кэширование секретаря
        """
        # Arrange
        user_id = 12345

        # Act - первый вызов должен создать нового секретаря
        secretary1 = await factory.get_user_secretary(user_id)

        # Act - второй вызов должен вернуть кэшированного секретаря
        secretary2 = await factory.get_user_secretary(user_id)

        # Assert
        assert secretary1 is not None
        assert secretary2 is not None
        assert secretary1 is secretary2  # Проверяем, что вернулся тот же объект
        mock_rest_client.get_user_secretary.assert_called_once_with(
            user_id
        )  # Проверяем, что API вызван только один раз

    @pytest.mark.asyncio
    async def test_different_users_get_different_secretaries(
        self, factory, mock_rest_client
    ):
        """
        Тест проверяет:
        1. Разные пользователи получают разных секретарей
        2. Кэш работает корректно для каждого пользователя
        """
        # Arrange
        user1_id = 12345
        user2_id = 67890

        # Настраиваем разные ответы для разных пользователей
        mock_rest_client.get_user_secretary.side_effect = [
            {
                "id": "secretary1",
                "name": "secretary1",
                "type": "llm",
                "instructions": "Ты - первый секретарь",
            },
            {
                "id": "secretary2",
                "name": "secretary2",
                "type": "llm",
                "instructions": "Ты - второй секретарь",
            },
        ]

        # Act
        secretary1 = await factory.get_user_secretary(user1_id)
        secretary2 = await factory.get_user_secretary(user2_id)

        # Assert
        assert secretary1 is not None
        assert secretary2 is not None
        assert secretary1 is not secretary2  # Проверяем, что это разные объекты
        assert (
            mock_rest_client.get_user_secretary.call_count == 2
        )  # Проверяем, что API вызван дважды

    @pytest.mark.asyncio
    async def test_secretary_processing_messages(self, factory, mock_rest_client):
        """
        Тест проверяет:
        1. Создание секретаря для пользователя
        2. Обработку сообщений через секретаря
        3. Корректность ответов
        """
        # Arrange
        user_id = 12345
        secretary = await factory.get_user_secretary(user_id)

        # Act
        message = HumanMessage(content="Привет! Как тебя зовут?")
        response = await secretary.process_message(message)

        # Assert
        assert response is not None
        assert isinstance(response, dict)
        assert "messages" in response
        last_message = self.get_last_assistant_message(response)
        assert last_message  # Проверяем, что есть ответ
        assert (
            "test_secretary" in last_message.lower()
        )  # Проверяем, что секретарь представился
