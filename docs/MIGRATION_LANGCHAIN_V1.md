# План миграции на LangChain/LangGraph 1.x

> **Цель:** Полный переход на LangChain 1.x и LangGraph 1.x без fallback-ов, обратной совместимости и legacy пакетов.
> **Принцип:** Только актуальные подходы. Никакого langchain-classic. Чистый современный код.
> **Сервис:** assistant_service
> **Оценка:** ~25-35 часов работы

## Содержание

1. [Текущее состояние](#текущее-состояние)
2. [Целевое состояние](#целевое-состояние)
3. [Breaking Changes](#breaking-changes)
4. [Итерации миграции](#итерации-миграции)
5. [Чек-лист готовности](#чек-лист-готовности)

---

## Текущее состояние

### Версии библиотек (после Итерации 1)
```toml
langchain = "^1.1.0"        # ОБНОВЛЕНО (было ^0.3.25)
langchain-openai = "^1.1.0" # ОБНОВЛЕНО (было ^0.3.11)
langchain-community = "^0.4.1" # ОБНОВЛЕНО (было ^0.3.20), удалим в Итерации 7
langchain-core = "^1.1.0"   # ОБНОВЛЕНО (было ^0.3.47)
langgraph = "^1.0.4"        # ОБНОВЛЕНО (было ^0.3.34)
```

### Используемые API

| Файл | Импорт | Статус в 1.x |
|------|--------|--------------|
| `langgraph_assistant.py` | `langgraph.prebuilt.create_react_agent` | **DEPRECATED** -> `langchain.agents.create_agent` |
| `graph_builder.py` | `langgraph.prebuilt.ToolNode, tools_condition` | Проверить совместимость |
| `graph_builder.py` | `langgraph.graph.END, START, StateGraph` | OK (core API) |
| `reducers.py` | `langgraph.graph.message.add_messages` | OK |
| `state.py` | `langchain_core.messages.BaseMessage` | OK |
| `*.py` | `langchain_core.messages.*` | OK |
| `*.py` | `langchain_core.tools.*` | OK |
| `langgraph_assistant.py` | `langchain_openai.ChatOpenAI` | OK |
| `tests/*.py` | `langgraph.checkpoint.*` | Проверить совместимость |

### Архитектура графа (текущая)

```
START -> save_input -> load_context -> retrieve_memories 
      -> [should_summarize?] -> summarize? -> assistant 
      -> [tools_condition?] -> tools? -> save_response -> finalize -> END
```

---

## Целевое состояние

### Версии библиотек
```toml
langchain = "^1.1.0"
langchain-openai = "^1.1.0"
langchain-core = "^1.1.0"
langgraph = "^1.0.4"
# langchain-community - УДАЛИТЬ если не нужен
# langchain-classic - НЕ ИСПОЛЬЗУЕМ
```

### Ключевые изменения

1. **`create_react_agent` -> `create_agent`** с middleware системой
2. **`AssistantState` наследует от `langchain.agents.AgentState`**
3. **Nodes переписаны как Middleware** (современный подход)
4. **Убран весь legacy код** - никаких chains, retrievers из старого API
5. **Только актуальные импорты** из `langchain.*`, `langchain_core.*`, `langgraph.*`

### Архитектура (целевая)

```
create_agent(
    model=ChatOpenAI,
    tools=[...],
    system_prompt=...,
    middleware=[
        MessageSaverMiddleware,      # before_agent: сохранение входящего
        ContextLoaderMiddleware,     # before_agent: загрузка контекста
        MemoryRetrievalMiddleware,   # before_model: RAG retrieval
        SummarizationMiddleware,     # before_model: суммаризация если нужно
        DynamicPromptMiddleware,     # before_model: динамический промпт
        ResponseSaverMiddleware,     # after_model: сохранение ответа
        FinalizerMiddleware,         # after_agent: финализация
    ],
    state_schema=AssistantState,
)
```

---

## Breaking Changes

### LangGraph 1.0

| Deprecated | Замена | Влияние |
|------------|--------|---------|
| `langgraph.prebuilt.create_react_agent` | `langchain.agents.create_agent` | **КРИТИЧНО** - полная переработка |
| `AgentState` из langgraph | `langchain.agents.AgentState` | Переписать state.py |
| `AgentStatePydantic` | TypedDict only | Уже TypedDict - OK |
| `ValidationNode` | Автоматическая валидация в create_agent | Не используется |
| `MessageGraph` | `StateGraph` с messages | Не используется |
| Python 3.9 | Python 3.10+ | OK (уже 3.11+) |

### LangChain 1.0

| Изменение | Влияние |
|-----------|---------|
| Namespace упрощен | Обновить все импорты |
| `prompt` -> `system_prompt` | Переименовать параметр |
| Dynamic prompts через `@dynamic_prompt` | Переписать prompt modifier |
| Pre/post hooks -> middleware с `before_model`/`after_model` | Переписать всю логику nodes |
| `response.text()` -> `response.text` | Property вместо метода |
| `AIMessage.example` удален | Не используем |
| Streaming node name: `"agent"` -> `"model"` | Обновить если используем |

### Что НЕ используем

- `langchain-classic` - никаких legacy chains
- `langchain.chains.*` - устаревший подход
- `langchain.retrievers.*` - если нужно, только через актуальный API
- `langchain.memory.*` - заменено на middleware + state
- Любые deprecated импорты из `langchain.schema`

---

## Итерации миграции

### Итерация 0: Подготовка (1-2 часа) - ЗАВЕРШЕНА

**Цель:** Создать изолированную среду для миграции

**Задачи:**
- [x] Создать ветку `feature/langchain-v1-migration`
- [x] Убедиться что все тесты проходят на текущей версии
- [x] Сделать backup текущего состояния

**Команды:**
```bash
git checkout -b feature/langchain-v1-migration
make test-unit SERVICE=assistant_service
make test-integration SERVICE=assistant_service
```

**Критерий завершения:** Все тесты зеленые, ветка создана - **ВЫПОЛНЕНО**

---

### Итерация 1: Обновление зависимостей (2-3 часа) - ЗАВЕРШЕНА

**Цель:** Обновить библиотеки до 1.x, сохранив работоспособность

**Задачи:**

1. [x] **Обновить pyproject.toml:**
```toml
[tool.poetry.dependencies]
langchain = "^1.1.0"
langchain-openai = "^1.1.0"
langchain-community = "^0.4.1"  # Сохранен, удалим в Итерации 7
langchain-core = "^1.1.0"
langgraph = "^1.0.4"
```

2. [x] **Обновить lock файл:**
```bash
cd assistant_service && poetry lock && poetry install
```

3. [x] **Запустить lint и тесты:**
```bash
make lint SERVICE=assistant_service
make test-unit SERVICE=assistant_service
```

4. [x] **Исправить первичные ошибки импортов:**
   - `CompiledGraph` -> `CompiledStateGraph` (langgraph 1.0 rename)
   - Import path: `langgraph.graph.graph` -> `langgraph.graph.state`

**Результат:**
- 32/32 тестов проходят
- 3 deprecation warnings о `create_react_agent` (ожидаемо, исправим в Итерации 3)

**Критерий завершения:** `poetry install` успешен, lint проходит - **ВЫПОЛНЕНО**

---

### Итерация 2: Миграция State (2-3 часа) - ОТЛОЖЕНА

**Цель:** Перевести AssistantState на новый базовый класс

**Статус:** Текущий `AssistantState` уже TypedDict и полностью совместим с LangGraph 1.x.
Миграция на `langchain.agents.AgentState` будет выполнена в Итерации 3 вместе с переходом на `create_agent`.

**Причина отложения:**
- Текущий state работает с кастомным графом (`build_full_graph`)
- `langchain.agents.AgentState` предназначен для использования с `create_agent`
- Нет смысла менять state отдельно от миграции на `create_agent`

**Файлы:**
- `src/assistants/langgraph/state.py`

**Задачи (будут выполнены в Итерации 3):**

1. [ ] **Обновить state.py:**

**До:**
```python
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

class AssistantState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], custom_message_reducer]
    # ...
```

**После:**
```python
from langchain.agents import AgentState as LangChainAgentState
from langchain_core.messages import BaseMessage
from typing_extensions import NotRequired

class AssistantState(LangChainAgentState):
    """Extended state for assistant with custom fields."""
    # messages уже есть в AgentState
    initial_message: BaseMessage
    user_id: str
    assistant_id: str
    llm_context_size: int
    triggered_event: NotRequired[QueueTrigger | None]
    log_extra: NotRequired[dict[str, Any] | None]
    initial_message_id: NotRequired[int | None]
    current_summary_content: NotRequired[str | None]
    newly_summarized_message_ids: NotRequired[list[int] | None]
    relevant_memories: NotRequired[list[dict[str, Any]] | None]
```

2. [ ] **Проверить совместимость reducer:**
   - Убедиться что `custom_message_reducer` совместим с новым AgentState
   - Возможно потребуется адаптация

3. [ ] **Обновить все импорты AssistantState** в других файлах

4. [ ] **Запустить тесты:**
```bash
make test-unit SERVICE=assistant_service
```

**Критерий завершения:** Все тесты с state проходят

---

### Итерация 3: Миграция на create_agent (6-8 часов) - ЗАВЕРШЕНА

**Цель:** Заменить create_react_agent на create_agent с middleware

**Файлы:**
- `src/assistants/langgraph/langgraph_assistant.py` - переписан
- `src/assistants/langgraph/middleware/` - создана новая директория с middleware
- `src/assistants/langgraph/graph_builder.py` - будет удален в Итерации 8

**Результат:**
- Создан `AssistantAgentState` наследующий от `langchain.agents.AgentState`
- Реализованы все middleware классы:
  - `MessageSaverMiddleware` (abefore_agent)
  - `ContextLoaderMiddleware` (abefore_agent)
  - `MemoryRetrievalMiddleware` (abefore_model)
  - `SummarizationMiddleware` (abefore_model)
  - `DynamicPromptMiddleware` (wrap_model_call)
  - `ResponseSaverMiddleware` (aafter_model)
  - `FinalizerMiddleware` (aafter_agent)
- `LangGraphAssistant` переписан на `create_agent` с middleware
- 32/32 тестов проходят

**Задачи:**

1. [x] **Создать middleware классы:**

**Файл:** `src/assistants/langgraph/middleware/__init__.py`
```python
from .summarization import SummarizationMiddleware
from .memory_retrieval import MemoryRetrievalMiddleware
from .context_loader import ContextLoaderMiddleware
from .response_saver import ResponseSaverMiddleware
```

2. [x] **Создать SummarizationMiddleware:**

**Файл:** `src/assistants/langgraph/middleware/summarization.py`
```python
from langchain.agents.middleware import AgentMiddleware, ModelRequest
from typing import Any

class SummarizationMiddleware(AgentMiddleware):
    """Middleware for summarizing conversation history."""
    
    def __init__(
        self,
        summary_llm,
        rest_client,
        summarization_prompt: str,
        threshold_percent: float = 0.6,
        messages_to_keep: int = 5,
    ):
        self.summary_llm = summary_llm
        self.rest_client = rest_client
        self.summarization_prompt = summarization_prompt
        self.threshold_percent = threshold_percent
        self.messages_to_keep = messages_to_keep
    
    def before_model(self, state, runtime) -> dict[str, Any] | None:
        """Check if summarization needed and perform it."""
        # Логика из should_summarize + summarize_history_node
        pass
```

3. [x] **Создать MemoryRetrievalMiddleware:**

**Файл:** `src/assistants/langgraph/middleware/memory_retrieval.py`
```python
from langchain.agents.middleware import AgentMiddleware
from typing import Any

class MemoryRetrievalMiddleware(AgentMiddleware):
    """Middleware for retrieving relevant memories from RAG."""
    
    def __init__(self, rag_client, limit: int = 5, threshold: float = 0.6):
        self.rag_client = rag_client
        self.limit = limit
        self.threshold = threshold
    
    def before_model(self, state, runtime) -> dict[str, Any] | None:
        """Retrieve memories and add to state."""
        # Логика из retrieve_memories_node
        pass
```

4. [x] **Создать DynamicPromptMiddleware:**

**Файл:** `src/assistants/langgraph/middleware/dynamic_prompt.py`
```python
from langchain.agents.middleware import dynamic_prompt, ModelRequest

@dynamic_prompt
def create_dynamic_prompt(request: ModelRequest) -> str:
    """Create dynamic system prompt based on state."""
    state = request.state
    memories = state.get("relevant_memories", [])
    summary = state.get("current_summary_content")
    
    memories_str = "\n".join(f"- {m.get('text', '')}" for m in memories) \
        if memories else "Нет сохраненной информации."
    summary_str = summary if summary else "Нет предыдущей истории."
    
    # Форматирование промпта
    return request.runtime.context.system_prompt_template.format(
        summary_previous=summary_str,
        memories=memories_str
    )
```

5. [x] **Переписать LangGraphAssistant:**

**До:**
```python
from langgraph.prebuilt import create_react_agent

self.agent_runnable = create_react_agent(
    self.llm,
    self.tools,
    prompt=self._add_system_prompt_modifier,
)
self.compiled_graph = build_full_graph(...)
```

**После:**
```python
from langchain.agents import create_agent

self.agent = create_agent(
    model=self.llm,
    tools=self.tools,
    system_prompt=self.system_prompt_template,  # или middleware
    middleware=[
        ContextLoaderMiddleware(rest_client=self.rest_client),
        MemoryRetrievalMiddleware(
            rag_client=self.rag_client,
            limit=self.memory_retrieve_limit,
            threshold=self.memory_retrieve_threshold,
        ),
        SummarizationMiddleware(
            summary_llm=self.llm,
            rest_client=self.rest_client,
            summarization_prompt=self.summarization_prompt,
        ),
        ResponseSaverMiddleware(rest_client=self.rest_client),
    ],
    state_schema=AssistantState,
)
```

6. [x] **Обновить process_message:**

**До:**
```python
final_state = await self.compiled_graph.ainvoke(input=dict(initial_state))
```

**После:**
```python
result = await self.agent.ainvoke(
    {"messages": [message]},
    context=Context(
        user_id=user_id,
        assistant_id=self.assistant_id,
        # ...
    )
)
```

7. [ ] **Удалить graph_builder.py** (перенесено в Итерацию 8)

8. [x] **Запустить тесты:**
```bash
make test-unit SERVICE=assistant_service
```

**Критерий завершения:** Agent создается и обрабатывает сообщения - **ВЫПОЛНЕНО**

---

### Итерация 4: Миграция Nodes -> Middleware (4-6 часов)

**Цель:** Перенести логику из nodes в middleware

**Файлы для миграции:**
- `nodes/save_message.py` -> `middleware/message_saver.py`
- `nodes/load_context.py` -> `middleware/context_loader.py`
- `nodes/retrieve_memories.py` -> `middleware/memory_retrieval.py`
- `nodes/summarize_history.py` -> `middleware/summarization.py`
- `nodes/save_response.py` -> `middleware/response_saver.py`
- `nodes/finalize_processing.py` -> `middleware/finalizer.py`

**Задачи:**

1. [ ] **MessageSaverMiddleware** (before_agent hook):
```python
class MessageSaverMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime) -> dict[str, Any] | None:
        """Save incoming message to database."""
        # Логика из save_input_message_node
        pass
```

2. [ ] **ContextLoaderMiddleware** (before_agent hook):
```python
class ContextLoaderMiddleware(AgentMiddleware):
    def before_agent(self, state, runtime) -> dict[str, Any] | None:
        """Load conversation context from database."""
        # Логика из load_context_node
        pass
```

3. [ ] **ResponseSaverMiddleware** (after_model hook):
```python
class ResponseSaverMiddleware(AgentMiddleware):
    def after_model(self, state, runtime) -> dict[str, Any] | None:
        """Save assistant response to database."""
        # Логика из save_response_node
        pass
```

4. [ ] **FinalizerMiddleware** (after_agent hook):
```python
class FinalizerMiddleware(AgentMiddleware):
    def after_agent(self, state, runtime) -> dict[str, Any] | None:
        """Finalize processing, update message statuses."""
        # Логика из finalize_processing_node
        pass
```

5. [ ] **Удалить директорию nodes/** после миграции

6. [ ] **Запустить тесты:**
```bash
make test-unit SERVICE=assistant_service
```

**Критерий завершения:** Все nodes перенесены, тесты проходят

---

### Итерация 5: Миграция Tools (2-3 часа)

**Цель:** Обновить tools для совместимости с 1.x

**Файлы:**
- `src/tools/base.py`
- `src/tools/factory.py`
- `src/tools/*.py`

**Задачи:**

1. [ ] **Проверить BaseTool совместимость:**
   - `langchain_core.tools.BaseTool` должен работать
   - Проверить `args_schema` handling

2. [ ] **Обновить импорты:**
```python
# Проверить что все импорты актуальны
from langchain.tools import tool, BaseTool
from langchain_core.tools import BaseTool as LangBaseTool
```

3. [ ] **Проверить tool error handling:**
   - В 1.x ошибки обрабатываются через `wrap_tool_call` middleware

4. [ ] **Запустить тесты tools:**
```bash
make test-unit SERVICE=assistant_service
```

**Критерий завершения:** Все tools работают с новым API

---

### Итерация 6: Миграция тестов (3-4 часа)

**Цель:** Обновить все тесты для 1.x API

**Файлы:**
- `tests/unit/assistants/test_langgraph_assistant.py`
- `tests/unit/orchestrator/test_orchestrator_message_processing.py`
- `tests/integration/conftest.py`
- `tests/unit/storage/skip_test_rest_checkpoint_saver.py`

**Задачи:**

1. [ ] **Обновить test_langgraph_assistant.py:**
   - Заменить моки для `create_react_agent` на `create_agent`
   - Обновить проверки state
   - Обновить checkpoint imports

2. [ ] **Обновить conftest.py:**
   - Обновить фикстуры для нового API
   - Проверить mock LLM совместимость

3. [ ] **Удалить skip_test_rest_checkpoint_saver.py:**
   - Если checkpointer больше не используется напрямую

4. [ ] **Запустить все тесты:**
```bash
make test-unit SERVICE=assistant_service
make test-integration SERVICE=assistant_service
```

**Критерий завершения:** Все тесты проходят

---

### Итерация 7: Удаление langchain-community (1-2 часа)

**Цель:** Убрать зависимость от langchain-community, использовать только актуальные пакеты

**Задачи:**

1. [ ] **Проверить использование langchain-community:**
```bash
grep -r "langchain_community" assistant_service/src/
grep -r "langchain-community" assistant_service/
```

2. [ ] **Если используется - найти замену:**
   - Векторные хранилища -> отдельные пакеты (`langchain-chroma`, `langchain-pinecone`, etc.)
   - Document loaders -> отдельные пакеты
   - Если нет замены - реализовать самостоятельно или использовать напрямую библиотеку провайдера

3. [ ] **Удалить из pyproject.toml:**
```toml
# УДАЛИТЬ эту строку:
# langchain-community = "^0.4.1"
```

4. [ ] **Обновить lock и проверить:**
```bash
cd assistant_service && poetry lock && poetry install
make test-unit SERVICE=assistant_service
```

**Критерий завершения:** langchain-community удален, тесты проходят

---

### Итерация 8: Очистка и удаление legacy кода (2-3 часа)

**Цель:** Удалить весь deprecated код и старые импорты

**Задачи:**

1. [ ] **Удалить файлы:**
   - [ ] `src/assistants/langgraph/nodes/` (вся директория)
   - [ ] `src/assistants/langgraph/graph_builder.py`
   - [ ] `src/assistants/langgraph/prompt_context_cache.py` (если не используется)

2. [ ] **Очистить импорты:**
   - [ ] Удалить все `from langgraph.prebuilt import create_react_agent`
   - [ ] Удалить все `from langgraph.checkpoint.*` если не используется

3. [ ] **Обновить reducers.py:**
   - Проверить совместимость с новым AgentState
   - Удалить неиспользуемый код

4. [ ] **Обновить utils/:**
   - Проверить `token_counter.py`
   - Проверить `logging_utils.py`

5. [ ] **Проверить все файлы на deprecated API:**
```bash
# Deprecated функции
grep -r "create_react_agent" assistant_service/
grep -r "langgraph.prebuilt" assistant_service/
grep -r "langchain.schema" assistant_service/

# Legacy пакеты (не должно быть!)
grep -r "langchain_community" assistant_service/
grep -r "langchain-community" assistant_service/
grep -r "langchain_classic" assistant_service/
grep -r "langchain-classic" assistant_service/

# Устаревшие импорты
grep -r "from langchain.chains" assistant_service/
grep -r "from langchain.memory" assistant_service/
grep -r "from langchain.retrievers" assistant_service/
```

6. [ ] **Запустить финальные тесты:**
```bash
make lint SERVICE=assistant_service
make test-unit SERVICE=assistant_service
make test-integration SERVICE=assistant_service
```

**Критерий завершения:** Нет упоминаний deprecated API

---

### Итерация 9: Документация и финализация (2-3 часа)

**Цель:** Обновить документацию и подготовить к merge

**Задачи:**

1. [ ] **Обновить AGENTS.md:**
   - Описать новую архитектуру с middleware
   - Обновить примеры кода
   - Обновить версии библиотек

2. [ ] **Обновить или удалить устаревшие docs/:**
   - [ ] `docs/assistant_refactoring_plan.md` - удалить если выполнен
   - [ ] `docs/memory_ideas1.md` - удалить устаревшие примеры с langchain.memory, langchain.chains
   - [ ] `docs/memory_ideas2.md` - удалить устаревшие примеры с langchain_community
   - [ ] Либо пометить эти файлы как ARCHIVED и не обновлять

3. [ ] **Создать CHANGELOG entry:**
```markdown
## [Unreleased]
### Changed
- Migrated to LangChain 1.x and LangGraph 1.x
- Replaced create_react_agent with create_agent + middleware
- Replaced graph nodes with middleware architecture
- Updated all imports to new namespaces

### Removed
- Removed langchain-community dependency
- Removed all deprecated imports (langchain.schema, langgraph.prebuilt.create_react_agent)
- Removed legacy graph nodes (replaced with middleware)
- Removed prompt_context_cache (replaced with middleware state)
```

4. [ ] **Тестирование на staging:**
```bash
docker-compose up --build -d
# Manual testing
```

5. [ ] **Code review и merge:**
```bash
git push origin feature/langchain-v1-migration
# Create PR
```

**Критерий завершения:** PR создан и одобрен

---

## Чек-лист готовности

### Перед началом миграции
- [ ] Все тесты проходят на текущей версии
- [ ] Создана ветка миграции
- [ ] Прочитана документация LangChain/LangGraph 1.x

### После каждой итерации
- [ ] `make lint SERVICE=assistant_service` проходит
- [ ] `make test-unit SERVICE=assistant_service` проходит
- [ ] Commit с описанием изменений

### Перед финальным merge
- [ ] Все unit тесты проходят
- [ ] Все integration тесты проходят
- [ ] Manual testing на staging
- [ ] Нет упоминаний deprecated API:
  ```bash
  grep -rE "(create_react_agent|langgraph\.prebuilt|langchain\.schema)" assistant_service/src/
  ```
- [ ] Нет legacy пакетов:
  ```bash
  grep -rE "(langchain_community|langchain_classic|langchain-community|langchain-classic)" assistant_service/
  ```
- [ ] Нет устаревших импортов:
  ```bash
  grep -rE "from langchain\.(chains|memory|retrievers)" assistant_service/src/
  ```
- [ ] pyproject.toml содержит только актуальные пакеты:
  - `langchain = "^1.1.0"`
  - `langchain-openai = "^1.1.0"`
  - `langchain-core = "^1.1.0"`
  - `langgraph = "^1.0.4"`
  - НЕТ `langchain-community`
  - НЕТ `langchain-classic`
- [ ] Документация обновлена
- [ ] CHANGELOG обновлен

---

## Откат (Rollback Plan)

Если миграция провалилась:

1. **Откат ветки:**
```bash
git checkout main
git branch -D feature/langchain-v1-migration
```

2. **Откат зависимостей:**
```bash
git checkout main -- assistant_service/pyproject.toml
git checkout main -- assistant_service/poetry.lock
```

3. **Rebuild:**
```bash
cd assistant_service && poetry install
make test-unit SERVICE=assistant_service
```

---

## Ссылки

- [LangChain v1 Release Notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [LangGraph v1 Release Notes](https://docs.langchain.com/oss/python/releases/langgraph-v1)
- [LangChain v1 Migration Guide](https://docs.langchain.com/oss/python/migrate/langchain-v1)
- [LangGraph v1 Migration Guide](https://docs.langchain.com/oss/python/migrate/langgraph-v1)
- [Middleware Documentation](https://docs.langchain.com/oss/python/langchain/middleware)
