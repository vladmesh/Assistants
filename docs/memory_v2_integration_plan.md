# Memory V2 Integration Plan

## Цель
Завершить интеграцию Memory V2 в assistant_service:
1. Автоматический retrieve релевантных воспоминаний перед ответом
2. Фоновое извлечение фактов через Batch API (экономия ~50%)
3. Полное удаление legacy кода (UserFact, UserSummary, старая суммаризация)

---

## Принципы

### Provider-Agnostic Design
Все компоненты системы должны быть независимы от конкретного LLM провайдера:
- Модель для извлечения фактов настраивается через глобальные настройки
- Batch API абстрагирован за интерфейсом (поддержка OpenAI, Google, Anthropic)
- Embedding модель также конфигурируема

### Configurable via Admin Panel
Все параметры настраиваются через админку (GlobalSettings):
- Частота batch extraction
- LLM модель для extraction
- Пороги similarity для дедупликации
- Лимиты на количество memories

---

## Архитектура

### Поток данных

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ONLINE (синхронно)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  User Message                                                       │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────┐    ┌──────────────────┐    ┌─────────────────┐    │
│  │ save_input  │───▶│ retrieve_memories│───▶│    assistant    │    │
│  └─────────────┘    └──────────────────┘    └─────────────────┘    │
│                            │                        │               │
│                            │ query = user_message   │               │
│                            ▼                        │               │
│                     ┌─────────────┐                 │               │
│                     │ RAG Service │                 │               │
│                     │  (search)   │                 │               │
│                     └─────────────┘                 │               │
│                            │                        │               │
│                            ▼                        ▼               │
│                     memories[] ──────────▶ system_prompt            │
│                                                     │               │
│                                                     ▼               │
│                                              ┌────────────┐         │
│                                              │   tools    │◀──┐     │
│                                              └────────────┘   │     │
│                                                     │         │     │
│                                                     ▼         │     │
│                                              ┌────────────┐   │     │
│                                              │MemorySave  │───┘     │
│                                              │   Tool     │         │
│                                              └────────────┘         │
│                                                     │               │
│                                                     ▼               │
│                                              save to Memory         │
│                                              (важные факты)         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                      OFFLINE (асинхронно)                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐                                                   │
│  │ cron_service │  (каждые N часов)                                 │
│  └──────────────┘                                                   │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────────────────────────────┐                           │
│  │ 1. Получить диалоги за последние N ч │                           │
│  │ 2. Сформировать batch request        │                           │
│  │ 3. Отправить в OpenAI/Google Batch   │                           │
│  └──────────────────────────────────────┘                           │
│         │                                                           │
│         ▼ (через ~24ч или раньше)                                   │
│  ┌──────────────────────────────────────┐                           │
│  │ 4. Получить результаты batch         │                           │
│  │ 5. Дедупликация фактов               │                           │
│  │ 6. Сохранить в Memory V2             │                           │
│  └──────────────────────────────────────┘                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Дедупликация и обработка противоречий

Проблема: LLM может извлечь факт "Пользователь любит Python" несколько раз, или факты могут противоречить друг другу ("Живу в Москве" → "Переехал в Питер").

**Решение: Семантический поиск близких фактов**

При создании/обновлении факта:
```
1. Генерируем embedding для нового факта
2. Ищем существующие факты с similarity > DEDUP_THRESHOLD (настраивается, default 0.85)
3. Если найден очень похожий (similarity > 0.95):
   - Обновляем существующий факт (перезаписываем text, обновляем timestamp)
4. Если найден похожий (0.85 < similarity < 0.95):
   - Обновляем существующий факт новым текстом (считаем что это уточнение/обновление)
5. Если нет похожих:
   - Создаем новый факт
```

**Пример:**
- Старый факт: "Живу в Москве" 
- Новый факт: "Переехал в Санкт-Петербург"
- similarity ~0.7 → создается новый факт (разные города)
- При поиске оба вернутся, LLM увидит контекст и поймет что переехал

- Старый факт: "Работаю программистом"
- Новый факт: "Работаю Python разработчиком"  
- similarity ~0.9 → обновляем старый факт на более конкретный

---

## Этап 1: Удаление Legacy кода

### 1.1 Файлы для удаления

**rest_service:**
- `src/models/user_fact.py` - модель UserFact
- `src/models/user_summary.py` - модель UserSummary  
- `src/crud/user_fact.py` - CRUD для UserFact
- `src/crud/user_summary.py` - CRUD для UserSummary
- `src/routers/user_facts.py` - роутер /users/{id}/facts
- `src/routers/user_summaries.py` - роутер /users/{id}/summaries
- `tests/routers/test_user_facts.py` - тесты
- `tests/test_user_summaries.py` - тесты

**shared_models:**
- `src/shared_models/api_schemas/user_fact.py` - схемы UserFact
- `src/shared_models/api_schemas/user_summary.py` - схемы UserSummary

**assistant_service:**
- `src/tools/user_fact_tool.py` - старый инструмент

### 1.2 Файлы для модификации

**rest_service:**
- `src/models/__init__.py` - убрать импорт UserFact, UserSummary
- `src/models/user.py` - убрать relationship user_facts, summaries
- `src/crud/__init__.py` - убрать импорты user_fact, user_summary
- `src/main.py` - убрать роутеры user_facts, user_summaries

**shared_models:**
- `src/shared_models/api_schemas/__init__.py` - убрать экспорты UserFact*, UserSummary*
- `src/shared_models/enums.py` - убрать USER_FACT enum (если не используется в memory_type)

**assistant_service:**
- `src/tools/__init__.py` - убрать UserFactTool
- `src/tools/factory.py` - убрать user_fact из маппинга
- `src/assistants/langgraph/state.py` - убрать user_facts поле
- `src/assistants/langgraph/constants.py` - убрать USER_FACTS_NAME, FACT_SAVE_TOOL_NAME
- `src/assistants/langgraph/nodes/load_context.py` - убрать загрузку user_facts
- `src/assistants/langgraph/nodes/summarize_history.py` - переписать/убрать
- `src/assistants/langgraph/langgraph_assistant.py` - убрать get_user_facts, references
- `src/services/rest_service.py` - убрать get_user_facts, get_user_summary, create_user_summary

### 1.3 Миграция БД
- Создать Alembic миграцию для удаления таблиц `user_facts`, `user_summaries`
- Убрать FK из других таблиц если есть

---

## Этап 2: Интеграция Memory Retrieve

### 2.1 Новый узел `retrieve_memories`

Создать `assistant_service/src/assistants/langgraph/nodes/retrieve_memories.py`:

```python
async def retrieve_memories_node(
    state: AssistantState,
    rag_client: RagServiceClient,
    limit: int = 5,
    threshold: float = 0.6,
) -> dict[str, Any]:
    """
    Retrieves relevant memories based on the incoming message.
    Adds them to the state for use in system prompt.
    """
    user_id = state.get("user_id")
    initial_message = state.get("initial_message")
    
    if not user_id or not initial_message:
        return {"relevant_memories": []}
    
    query = initial_message.content
    
    try:
        memories = await rag_client.search_memories(
            query=query,
            user_id=int(user_id),
            limit=limit,
            threshold=threshold,
        )
        return {"relevant_memories": memories}
    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        return {"relevant_memories": []}
```

### 2.2 Обновление State

```python
class AssistantState(TypedDict):
    # ... existing fields ...
    relevant_memories: list[dict] | None  # Retrieved memories for current request
```

### 2.3 Обновление Graph Builder

```python
# После load_context, добавить retrieve_memories
builder.add_edge("save_input", "retrieve_memories")
builder.add_edge("retrieve_memories", "assistant")

# Или с условием (если хотим пропускать при пустом сообщении)
builder.add_conditional_edges(
    "save_input",
    should_retrieve_memories,  # проверка нужен ли retrieve
    {
        "retrieve": "retrieve_memories",
        "skip": "assistant",
    }
)
```

### 2.4 Обновление System Prompt

Добавить секцию с воспоминаниями:

```python
SYSTEM_PROMPT_TEMPLATE = """
...existing prompt...

## Известная информация о пользователе:
{memories}
"""
```

Форматирование memories в промпте:
```python
def format_memories_for_prompt(memories: list[dict]) -> str:
    if not memories:
        return "Нет сохранённой информации."
    
    lines = []
    for m in memories:
        text = m.get("text", "")
        memory_type = m.get("memory_type", "")
        lines.append(f"- [{memory_type}] {text}")
    
    return "\n".join(lines)
```

---

## Этап 3: Фоновое извлечение фактов (Batch API)

### 3.1 Расширение GlobalSettings

Модель `GlobalSettings` уже существует в `rest_service/src/models/global_settings.py`:

```python
# Текущие поля:
class GlobalSettings(BaseModel, table=True):
    id: int | None = Field(default=1, primary_key=True)
    summarization_prompt: str  # Можно удалить после cleanup
    context_window_size: int = Field(default=4096)
```

**Добавить новые поля для Memory V2:**

```python
class GlobalSettings(BaseModel, table=True):
    id: int | None = Field(default=1, primary_key=True)
    
    # --- Existing (будет удалено после cleanup) ---
    summarization_prompt: str = Field(default="...")  # TODO: удалить
    context_window_size: int = Field(default=4096)
    
    # --- Memory Extraction Settings ---
    memory_extraction_enabled: bool = Field(default=True)
    memory_extraction_interval_hours: int = Field(
        default=24, 
        description="How often to run batch extraction"
    )
    memory_extraction_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model for fact extraction"
    )
    memory_extraction_provider: str = Field(
        default="openai",
        description="Provider: openai, google, anthropic"
    )
    
    # --- Deduplication Settings ---
    memory_dedup_threshold: float = Field(
        default=0.85,
        description="Similarity threshold for deduplication"
    )
    memory_update_threshold: float = Field(
        default=0.95,
        description="Similarity threshold for updating existing fact"
    )
    
    # --- Embedding Settings ---
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Model for generating embeddings"
    )
    embedding_provider: str = Field(
        default="openai",
        description="Provider for embeddings"
    )
    
    # --- Limits ---
    max_memories_per_user: int = Field(
        default=1000,
        description="Maximum memories per user (for retention policy)"
    )
    memory_retrieve_limit: int = Field(
        default=5,
        description="Default number of memories to retrieve"
    )
    memory_retrieve_threshold: float = Field(
        default=0.6,
        description="Default similarity threshold for retrieval"
    )
```

**Также обновить схемы в `shared_models/src/shared_models/api_schemas/global_settings.py`:**
- `GlobalSettingsBase` - добавить новые поля
- `GlobalSettingsRead` - наследует от Base
- `GlobalSettingsUpdate` - все поля опциональны

### 3.2 Provider-Agnostic LLM Client

Создать абстракцию для работы с разными провайдерами:

```python
# shared_models или отдельный пакет llm_client

from abc import ABC, abstractmethod
from typing import Protocol

class LLMProvider(Protocol):
    """Protocol for LLM providers."""
    
    async def complete(self, prompt: str, model: str) -> str:
        """Generate completion."""
        ...
    
    async def submit_batch(self, requests: list[dict], model: str) -> str:
        """Submit batch request, return batch_id."""
        ...
    
    async def get_batch_status(self, batch_id: str) -> str:
        """Get batch status: pending, completed, failed."""
        ...
    
    async def get_batch_results(self, batch_id: str) -> list[dict]:
        """Get batch results."""
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI implementation."""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
    
    async def submit_batch(self, requests: list[dict], model: str) -> str:
        # OpenAI Batch API implementation
        ...


class GoogleProvider(LLMProvider):
    """Google Vertex AI implementation."""
    
    async def submit_batch(self, requests: list[dict], model: str) -> str:
        # Google Batch Prediction implementation
        ...


class AnthropicProvider(LLMProvider):
    """Anthropic implementation (Message Batches API)."""
    
    async def submit_batch(self, requests: list[dict], model: str) -> str:
        # Anthropic Message Batches implementation
        ...


def get_llm_provider(provider_name: str) -> LLMProvider:
    """Factory for LLM providers."""
    providers = {
        "openai": OpenAIProvider,
        "google": GoogleProvider,
        "anthropic": AnthropicProvider,
    }
    return providers[provider_name](...)
```

### 3.3 Memory Extraction Job

`cron_service/src/jobs/memory_extraction.py`:

```python
class MemoryExtractionJob:
    """
    Периодически извлекает факты из диалогов через Batch API.
    Настройки берутся из GlobalSettings.
    """
    
    def __init__(self, rest_client: RestServiceClient):
        self.rest_client = rest_client
        self._settings: GlobalSettings | None = None
        self._llm_provider: LLMProvider | None = None
    
    async def get_settings(self) -> GlobalSettings:
        """Fetch current settings from REST API."""
        if not self._settings:
            self._settings = await self.rest_client.get_global_settings()
        return self._settings
    
    async def get_provider(self) -> LLMProvider:
        """Get configured LLM provider."""
        settings = await self.get_settings()
        return get_llm_provider(settings.memory_extraction_provider)
    
    async def run(self):
        settings = await self.get_settings()
        
        if not settings.memory_extraction_enabled:
            logger.info("Memory extraction is disabled")
            return
        
        provider = await self.get_provider()
        
        # 1. Получить диалоги за последние N часов
        conversations = await self.get_recent_conversations(
            hours=settings.memory_extraction_interval_hours
        )
        
        # 2. Для каждого пользователя/ассистента
        for conv in conversations:
            # 3. Получить существующие факты для контекста
            existing_facts = await self.get_existing_facts(conv.user_id)
            
            # 4. Сформировать batch request
            batch_request = self.create_batch_request(
                conv, 
                existing_facts,
                model=settings.memory_extraction_model
            )
            
            # 5. Отправить в Batch API
            batch_id = await provider.submit_batch(
                batch_request, 
                model=settings.memory_extraction_model
            )
            
            # 6. Сохранить batch_id для отслеживания
            await self.save_batch_job(batch_id, conv.user_id)
    
    async def process_completed_batches(self):
        settings = await self.get_settings()
        provider = await self.get_provider()
        
        pending_jobs = await self.get_pending_batch_jobs()
        
        for job in pending_jobs:
            status = await provider.get_batch_status(job.batch_id)
            
            if status == "completed":
                results = await provider.get_batch_results(job.batch_id)
                
                # Дедупликация с настраиваемым threshold
                unique_facts = await self.deduplicate_facts(
                    new_facts=results,
                    user_id=job.user_id,
                    threshold=settings.memory_dedup_threshold,
                    update_threshold=settings.memory_update_threshold,
                )
                
                for fact in unique_facts:
                    await self.save_memory(fact)
                
                await self.mark_job_completed(job.id)
```

### 3.4 Промпт для извлечения фактов

```python
FACT_EXTRACTION_PROMPT = """
Проанализируй диалог и извлеки важные факты о пользователе.

## Типы фактов:
- user_fact: личная информация (имя, возраст, профессия)
- preference: предпочтения (любит/не любит)
- event: важные события (день рождения, встречи)
- conversation_insight: инсайты из разговора

## Уже известные факты (НЕ ПОВТОРЯЙ):
{existing_facts}

## Диалог:
{conversation}

## Инструкции:
1. Извлекай только НОВУЮ информацию
2. Формулируй кратко и конкретно
3. Указывай тип и важность (1-10)
4. Не дублируй известные факты

Ответ в формате JSON:
[
  {"text": "...", "memory_type": "...", "importance": N},
  ...
]
"""
```

### 3.5 Дедупликация

```python
async def deduplicate_facts(
    self,
    new_facts: list[dict],
    user_id: int,
    threshold: float = 0.85,
    update_threshold: float = 0.95,
) -> list[dict]:
    """
    Фильтрует и обрабатывает факты на основе similarity.
    
    Args:
        threshold: Порог для определения "похожести" (default из GlobalSettings)
        update_threshold: Порог для обновления существующего факта
    
    Логика:
        - similarity > update_threshold: обновляем существующий факт
        - threshold < similarity <= update_threshold: обновляем существующий
        - similarity <= threshold: создаем новый факт
    """
    unique = []
    
    for fact in new_facts:
        # Генерируем embedding для нового факта
        embedding = await self.generate_embedding(fact["text"])
        
        # Ищем похожие существующие
        similar = await self.rag_client.search_memories(
            embedding=embedding,
            user_id=user_id,
            limit=1,
            threshold=threshold,
        )
        
        if not similar:
            # Нет похожих - добавляем как новый
            unique.append(fact)
        else:
            existing = similar[0]
            similarity = existing.get("score", 0)
            
            # Обновляем существующий факт новой информацией
            await self.update_memory(
                memory_id=existing["id"],
                text=fact["text"],
                importance=max(existing.get("importance", 1), fact.get("importance", 1)),
            )
            logger.info(
                f"Updated existing memory {existing['id']} "
                f"(similarity={similarity:.2f})"
            )
    
    return unique
```

### 3.6 Модель для отслеживания batch jobs

Добавить в rest_service:

```python
class BatchJob(BaseModel, table=True):
    """Tracks batch API jobs for memory extraction."""
    
    __tablename__ = "batch_jobs"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    batch_id: str = Field(index=True)  # ID от OpenAI/Google
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    status: str = Field(default="pending")  # pending, completed, failed
    job_type: str = Field(default="memory_extraction")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    error_message: str | None = None
```

---

## Этап 4: Обновление суммаризации (опционально)

### Вариант A: Удалить полностью
- Удалить `summarize_history_node`
- Memory V2 заменяет суммаризацию семантическим поиском
- Плюс: Простота, нет дублирования
- Минус: Нет "краткого" контекста всего диалога

### Вариант B: Адаптировать под Memory V2
- Суммари сохраняется как Memory с типом `conversation_summary`
- При retrieve подтягивается последнее суммари + релевантные факты
- Плюс: Сохраняем контекст диалога
- Минус: Сложнее, больше данных

### Рекомендация: Вариант A для MVP
Начать без суммаризации. Если понадобится контекст всего диалога - добавить как тип Memory.

---

## План работ

### Фаза 1: Cleanup (1 день) ✅ DONE
- [x] Удалить legacy модели и код (UserFact, UserSummary)
- [x] Создать миграцию для удаления таблиц
- [x] Удалить/обновить связанные тесты
- [x] Убрать user_facts из графа (суммаризация оставлена для управления контекстом)

### Фаза 2: GlobalSettings & Provider Abstraction (1 день) ✅ DONE
- [x] Расширить существующую модель GlobalSettings новыми полями (см. 3.1)
- [x] Обновить схемы в shared_models
- [x] Создать Alembic миграцию для новых полей
- [x] Создать LLMProvider protocol и реализации (OpenAI)

### Фаза 3: Memory Retrieve (1 день) ✅ DONE
- [x] Создать узел `retrieve_memories`
- [x] Обновить AssistantState (уже есть `relevant_memories`)
- [x] Интегрировать в граф (после load_context, перед assistant)
- [x] Обновить system prompt template (уже поддерживает `{memories}`)
- [x] Использовать настройки из GlobalSettings (retrieve_limit, threshold)
- [x] Обновить UI в админке для новых GlobalSettings полей

### Фаза 4: Testing & Polish (1 день)
- [ ] Интеграционные тесты для retrieve_memories
- [ ] Проверить end-to-end flow
- [ ] Тюнинг threshold и limit параметров

### Фаза 5: Batch Extraction Infrastructure (отложено)
- [ ] Добавить модель BatchJob
- [ ] Создать MemoryExtractionJob в cron_service
- [ ] Реализовать job для извлечения фактов
- [ ] Реализовать job для обработки результатов
- [ ] Добавить семантическую дедупликацию

---

## Открытые вопросы

1. **Приватность**: Нужно ли шифрование memories?

---

## Решенные вопросы

1. ~~**Batch API provider**~~: Provider-agnostic, настраивается в GlobalSettings
2. ~~**Частота batch extraction**~~: Настраивается в GlobalSettings (`memory_extraction_interval_hours`)
3. ~~**Конфликты фактов**~~: Семантический поиск близких + обновление существующих
4. ~~**Retention policy**~~: Хранить memories вечно (без decay)
