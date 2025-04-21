# tests/test_memory_pipeline_e2e.py
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# Импорты из нашего кода (пути абсолютные от корня проекта, т.к. тесты запускаются оттуда)
from assistants.langgraph.graph_builder import build_full_graph
from assistants.langgraph.state import AssistantState
from config.settings import Settings  # Импортируем Settings из правильного модуля
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, Tool  # Для мока инструментов
from langgraph.checkpoint.memory import (
    MemorySaver,  # Используем MemorySaver для простоты
)

# from langgraph.graph import CompiledGraph # OLD IMPORT
# from langgraph.pregel import CompiledGraph # Incorrect import from previous attempt
from langgraph.graph.state import (
    CompiledGraph,  # CORRECT IMPORT based on graph_builder.py
)

# Импорт сервисов/утилит
from services.rest_service import RestServiceClient

# Импортируем схему и сам инструмент
from tools.user_fact_tool import UserFactTool

# --- Фикстуры и Моки ---


@pytest.fixture
def mock_rest_client() -> MagicMock:
    """Фикстура для мока RestServiceClient."""
    client = MagicMock(spec=RestServiceClient)
    # Настроим async методы
    client.get_user_facts = AsyncMock(return_value=["Initial fact 1"])  # Пример ответа
    client.save_user_fact = AsyncMock(return_value={"success": True})  # Пример ответа
    # Applying fix: Comment out lines causing AttributeError
    # client.__aenter__ = AsyncMock(return_value=client)
    # client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_llm() -> MagicMock:
    """Фикстура для мока основного LLM."""
    llm = MagicMock(spec=BaseChatModel)
    # Настроить стандартный ответ, можно переопределять в тестах
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked LLM response"))
    # Добавим другие возможные методы, если они используются
    llm.bind_tools = MagicMock(return_value=llm)  # Часто используется
    return llm


@pytest.fixture
def mock_summary_llm() -> MagicMock:
    """Фикстура для мока LLM для суммарризации."""
    llm = MagicMock(spec=BaseChatModel)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Mocked summary"))
    return llm


@pytest.fixture
def memory_saver() -> MemorySaver:
    """Фикстура для in-memory checkpointer."""
    return MemorySaver()


@pytest.fixture
def mock_settings() -> MagicMock:
    """Фикстура для мока настроек."""
    settings = MagicMock(spec=Settings)
    # Можно добавить дефолтные значения для настроек, если они нужны
    settings.user_facts_collection_name = "mock_user_facts"
    return settings


@pytest.fixture
def user_fact_tool(
    mock_rest_client: MagicMock, mock_settings: MagicMock
) -> UserFactTool:
    """Фикстура для создания реального UserFactTool с моками зависимостей."""
    # Создаем реальный экземпляр инструмента, передавая моки
    # Добавляем обязательные name и description для BaseTool
    tool = UserFactTool(
        name="save_user_fact",
        description="Saves a specific fact about the user to the knowledge base.",
        rest_client=mock_rest_client,
        settings=mock_settings,
    )
    # Нам нужно замокать только _arun, т.к. он вызывается LangGraph
    # При этом args_schema и другие атрибуты останутся реальными
    # Не будем мокать _arun здесь, langgraph должен вызвать его как есть,
    # а он внутри уже вызовет мокнутый mock_rest_client.save_user_fact
    return tool


@pytest.fixture
def compiled_test_graph(
    mock_llm: MagicMock,
    mock_summary_llm: MagicMock,
    mock_rest_client: MagicMock,
    memory_saver: MemorySaver,
    user_fact_tool: UserFactTool,  # Принимаем реальный UserFactTool
) -> CompiledGraph:
    """Фикстура для сборки графа с моками."""
    real_tools = [user_fact_tool]  # Используем реальный инструмент
    # Мок функции узла ассистента, чтобы не зависеть от create_react_agent
    mock_run_node_fn = AsyncMock(return_value={})

    graph = build_full_graph(
        run_node_fn=mock_run_node_fn,
        tools=real_tools,
        checkpointer=memory_saver,
        rest_client=mock_rest_client,
        system_prompt_text="Test system prompt",
        summary_llm=mock_summary_llm,
    )
    return graph


# --- Тесты ---


# TODO: Добавить остальные тесты из плана
