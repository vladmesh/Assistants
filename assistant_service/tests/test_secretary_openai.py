from typing import Optional

import pytest
from assistants.llm_chat import BaseLLMChat
from assistants.openai_assistant import OpenAIAssistant
from langchain.tools import BaseTool
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tools.base import ToolAssistant


@pytest.mark.external_api
class TestSecretaryOpenAI:
    """Тесты для секретаря на основе OpenAI API без инструментов и субассистентов"""

    @pytest.mark.asyncio
    async def test_basic_conversation(self, openai_assistant_id):
        """
        Тест проверяет:
        1. Создание секретаря на основе OpenAI API
        2. Отправку простого сообщения
        3. Получение осмысленного ответа
        """
        # Skip test if no assistant ID provided
        if not openai_assistant_id:
            pytest.skip("OPENAI_ASSISTANT_ID not set")

        # Arrange
        secretary = OpenAIAssistant(
            assistant_id=openai_assistant_id,
            name="test_secretary",
            instructions=(
                "Ты - ассистент по имени test_secretary. Всегда представляйся этим"
                " именем, когда тебя спрашивают как тебя зовут."
            ),
        )

        # Act
        message = HumanMessage(content="Привет! Как тебя зовут?")
        response = await secretary.process_message(message)

        # Debug output
        print(f"\nAssistant response: {response}\n")

        # Assert
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        # Ассистент может представиться по-разному, проверяем что
        # он вообще как-то отвечает
        # на вопрос об имени
        assert any(
            word in response.lower()
            for word in ["зовут", "имя", "называть", "assistant", "ассистент"]
        )

    @pytest.mark.asyncio
    async def test_assistant_with_tools(self, openai_assistant_id):
        """
        Тест проверяет:
        1. Создание секретаря с инструментами
        2. Обработку сообщения, требующего использования инструмента
        3. Корректный вызов инструмента и обработку результата
        """
        if not openai_assistant_id:
            pytest.skip("OPENAI_ASSISTANT_ID not set")

        # Создаем простой тестовый инструмент
        class TestTool(BaseTool):
            name: str = "get_current_time"
            description: str = "Get current time"

            def _run(self, **kwargs) -> str:
                raise NotImplementedError("Use async version")

            async def _arun(self, **kwargs) -> str:
                return "12:00 PM"

        # Arrange
        tool_schema = {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get current time",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }

        secretary = OpenAIAssistant(
            assistant_id=openai_assistant_id,
            name="test_secretary",
            instructions=(
                "Ты - ассистент по имени test_secretary. Используй инструмент"
                " get_current_time, когда тебя спрашивают о времени."
            ),
            tools=[tool_schema],
            tool_instances=[TestTool()],
        )

        # Act
        message = HumanMessage(content="Который сейчас час?")
        response = await secretary.process_message(message)

        # Debug output
        print(f"\nAssistant response with tool: {response}\n")

        # Assert
        assert response is not None
        assert isinstance(response, str)
        assert len(response) > 0
        assert "12:00" in response

    @pytest.mark.asyncio
    async def test_assistant_with_subassistant(self, openai_assistant_id):
        """
        Тест проверяет:
        1. Создание секретаря на основе OpenAI API с суб-ассистентом на основе LangGraph
        2. Делегирование запроса суб-ассистенту с правильными параметрами
        3. Корректную передачу ответа от суб-ассистента пользователю
        """
        if not openai_assistant_id:
            pytest.skip("OPENAI_ASSISTANT_ID not set")

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
                    description=(
                        "Ask expert assistant for help with technical questions"
                    ),
                    assistant=assistant,
                )

            def _run(self, question: str) -> str:
                raise NotImplementedError("Use async version")

            async def _arun(self, message: str) -> str:
                return await self.assistant.process_message(message)

        # Arrange - создаем основного ассистента на основе OpenAI API
        sub_assistant_tool = SubAssistantTool(mock_sub_assistant)

        secretary = OpenAIAssistant(
            assistant_id=openai_assistant_id,
            name="test_secretary",
            instructions="""Ты - ассистент по имени test_secretary.

            Используй инструмент ask_expert ТОЛЬКО для технических вопросов, таких как:
            - Вопросы о компьютерах и технологиях
            - Вопросы о научных концепциях
            - Вопросы о технических устройствах и их работе

            НЕ используй ask_expert для обычных вопросов о погоде, времени, и других не
            технических тем.

            ВАЖНО: Когда получаешь ответ от ask_expert, ты ДОЛЖЕН вернуть его
            пользователю ТОЧНО в том виде, в каком получил, БЕЗ КАКИХ-ЛИБО
            ИЗМЕНЕНИЙ. Не убирай префикс "Технический ответ:", не изменяй
            формулировки, не добавляй свой текст до или после.
            """,
            tools=[sub_assistant_tool.openai_schema],
            tool_instances=[sub_assistant_tool],
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
            responses.append(response)
            print(f"\nQuestion: {question}")
            print(f"Response: {response}\n")

        # Assert
        # 1. Проверяем, что суб-ассистент был вызван для технических вопросов
        assert len(mock_sub_assistant.calls) == 2  # Должен быть вызван для двух
        # технических вопросов
        assert "квантовый компьютер" in mock_sub_assistant.calls[0]["message"]
        assert "нейронная сеть" in mock_sub_assistant.calls[1]["message"]

        # 2. Проверяем, что ответы на технические вопросы содержат маркер от
        # суб-ассистента
        assert "Технический ответ:" in responses[0]  # квантовый компьютер
        assert "Технический ответ:" not in responses[1]  # погода

        # 3. Проверяем, что в ответах содержатся оригинальные вопросы
        assert "квантовый компьютер" in responses[0]
        assert "нейронная сеть" in responses[2]
