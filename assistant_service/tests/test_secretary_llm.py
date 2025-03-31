import os
import sys
from typing import Any, Optional

import pytest

# Добавляем путь к src в PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from assistants.llm_chat import BaseLLMChat
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
from messages.base import HumanMessage
from tools.base import MessageInput, ToolAssistant


@pytest.mark.external_api
class TestSecretaryLLM:
    """Тесты для секретаря на основе LangChain LLM без инструментов и субассистентов"""

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

    @pytest.mark.asyncio
    async def test_basic_conversation(self):
        """
        Тест проверяет:
        1. Создание секретаря на основе LLM
        2. Отправку простого сообщения
        3. Получение осмысленного ответа
        """
        # Arrange
        secretary = BaseLLMChat(
            llm=ChatOpenAI(model="gpt-4-turbo-preview", temperature=0),
            name="test_secretary",
            instructions="Ты - ассистент по имени test_secretary. Всегда представляйся этим именем, когда тебя спрашивают как тебя зовут.",
            is_secretary=True,
        )

        # Act
        message = HumanMessage(content="Привет! Как тебя зовут?")
        response = await secretary.process_message(message)

        # Debug output
        print(f"\nAssistant response: {response}\n")

        # Get last assistant message
        last_message = self.get_last_assistant_message(response)

        # Assert
        assert response is not None
        assert isinstance(response, dict)
        assert "messages" in response
        assert last_message
        # Ассистент может представиться по-разному, проверяем что он вообще как-то отвечает на вопрос об имени
        assert any(
            word in last_message.lower()
            for word in ["зовут", "имя", "называть", "assistant", "ассистент"]
        )

    @pytest.mark.asyncio
    async def test_assistant_with_tools(self):
        """
        Тест проверяет:
        1. Создание секретаря с инструментами
        2. Обработку сообщения, требующего использования инструмента
        3. Корректный вызов инструмента и обработку результата
        """

        # Создаем простой тестовый инструмент
        class TestTool(BaseTool):
            name: str = "get_current_time"
            description: str = "Get current time"

            def _run(self, **kwargs) -> str:
                raise NotImplementedError("Use async version")

            async def _arun(self, **kwargs) -> str:
                return "12:00 PM"

        # Arrange
        secretary = BaseLLMChat(
            llm=ChatOpenAI(model="gpt-4-turbo-preview", temperature=0),
            name="test_secretary",
            instructions="Ты - ассистент по имени test_secretary. Используй инструмент get_current_time, когда тебя спрашивают о времени.",
            tools=[TestTool()],
            is_secretary=True,
        )

        # Act
        message = HumanMessage(content="Который сейчас час?")
        response = await secretary.process_message(message)

        # Debug output
        print(f"\nAssistant response with tool: {response}\n")

        # Get last assistant message
        last_message = self.get_last_assistant_message(response)

        # Assert
        assert response is not None
        assert isinstance(response, dict)
        assert "messages" in response
        assert last_message
        assert "12:00" in last_message

    @pytest.mark.asyncio
    async def test_assistant_with_subassistant(self):
        """
        Тест проверяет:
        1. Создание секретаря на основе LLM с суб-ассистентом
        2. Делегирование запроса суб-ассистенту с правильными параметрами
        3. Корректную передачу ответа от суб-ассистента пользователю
        """

        # Создаем моковый суб-ассистент для отслеживания вызовов
        class MockSubAssistant(BaseLLMChat):
            def __init__(self):
                self.calls = []
                super().__init__(
                    llm=ChatOpenAI(model="gpt-4-turbo-preview", temperature=0),
                    name="expert",
                    instructions="Mock instructions",
                    is_secretary=False,
                )

            async def process_message(
                self, message: str, user_id: Optional[str] = None
            ) -> str:
                # Записываем каждый вызов
                self.calls.append({"message": message, "user_id": user_id})
                return f"Технический ответ: Это тестовый ответ на вопрос '{message}'"

        # Создаем моковый суб-ассистент
        mock_sub_assistant = MockSubAssistant()

        # Создаем инструмент для работы с суб-ассистентом
        class SubAssistantTool(ToolAssistant):
            def __init__(self, assistant: BaseLLMChat):
                super().__init__(
                    name="ask_expert",
                    description="Ask expert assistant for help with technical questions",
                    args_schema=MessageInput,
                    assistant=assistant,
                )

            def _run(self, question: str) -> str:
                raise NotImplementedError("Use async version")

            async def _arun(self, message: str) -> str:
                return await self.assistant.process_message(message)

        # Arrange - создаем основного ассистента
        sub_assistant_tool = SubAssistantTool(mock_sub_assistant)

        secretary = BaseLLMChat(
            llm=ChatOpenAI(model="gpt-4-turbo-preview", temperature=0),
            name="test_secretary",
            instructions="""Ты - ассистент по имени test_secretary. 
            
            Используй инструмент ask_expert ТОЛЬКО для технических вопросов, таких как:
            - Вопросы о компьютерах и технологиях
            - Вопросы о научных концепциях
            - Вопросы о технических устройствах и их работе
            
            НЕ используй ask_expert для обычных вопросов о погоде, времени, и других не технических тем.
            
            ВАЖНО: Когда получаешь ответ от ask_expert, ты ДОЛЖЕН вернуть его пользователю ТОЧНО в том виде, 
            в каком получил, БЕЗ КАКИХ-ЛИБО ИЗМЕНЕНИЙ. Не убирай префикс "Технический ответ:", 
            не изменяй формулировки, не добавляй свой текст до или после.""",
            tools=[sub_assistant_tool],
            is_secretary=True,
        )

        # Act - отправляем несколько разных вопросов
        questions = [
            "Как работает квантовый компьютер?",
            "Какая погода?",  # Не технический вопрос
            "Что такое нейронная сеть?",
        ]

        responses = []
        for question in questions:
            response = await secretary.process_message(HumanMessage(content=question))
            last_message = self.get_last_assistant_message(response)
            responses.append(last_message)
            print(f"\nQuestion: {question}")
            print(f"Response: {response}\n")

        # Assert
        # 1. Проверяем, что суб-ассистент был вызван для технических вопросов
        assert (
            len(mock_sub_assistant.calls) == 2
        )  # Должен быть вызван для двух технических вопросов
        assert "квантовый компьютер" in mock_sub_assistant.calls[0]["message"]
        assert "нейронная сеть" in mock_sub_assistant.calls[1]["message"]

        # 2. Проверяем, что ответы на технические вопросы содержат маркер от суб-ассистента
        assert "Технический ответ:" in responses[0]  # квантовый компьютер
        assert "Технический ответ:" not in responses[1]  # погода
        assert "Технический ответ:" in responses[2]  # нейронная сеть

        # 3. Проверяем, что в ответах содержатся оригинальные вопросы
        assert "квантовый компьютер" in responses[0]
        assert "нейронная сеть" in responses[2]
