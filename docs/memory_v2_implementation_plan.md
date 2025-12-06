# План реализации Memory V2 (Unified Memory)

## Цель
Создать единую систему долгосрочной памяти для ассистентов, объединяющую факты, саммари диалогов и извлеченные знания. Переход от разрозненных таблиц (`UserFact`, `UserSummary`) к единой сущности `Memory` с векторным поиском (pgvector).

## Архитектурные решения

### 1. Хранилище: PostgreSQL + pgvector
- Используем существующий PostgreSQL в `rest_service`.
- **Важно:** Необходимо обновить Docker-образ базы данных на `pgvector/pgvector:pg16` для поддержки векторных операций.
- В `rest_service` добавляем библиотеку `pgvector` для работы с векторами через SQLAlchemy.

### 2. Разделение ответственности (RAG vs REST)
- **REST Service (`rest_service`):**
    - Отвечает за **хранение** данных и **базовый векторный поиск**.
    - Предоставляет "глупый" endpoint `POST /memories/search`, который принимает вектор и возвращает Top-K ближайших записей из БД.
    - Не знает про OpenAI, эмбеддинги и сложную логику ранжирования.
- **RAG Service (`rag_service`):**
    - Остается "мозгом" поиска.
    - Принимает текстовые запросы от Ассистента.
    - Генерирует эмбеддинги (через OpenAI).
    - Вызывает `rest_service` для получения кандидатов.
    - (В будущем) Реализует Reranking, Hybrid Search и сложную фильтрацию.

### 3. Модель эмбеддингов
- Используем **`text-embedding-3-small`**.
- Размерность: 1536.
- Причина: Дешевле, быстрее и качественнее, чем `ada-002`.

---

## Этап 1: Инфраструктура и База Данных

### 1.1 Обновление Docker Compose
- [x] Заменить образ `db` в `docker-compose.yml` на `pgvector/pgvector:pg16`.
- [x] Убедиться, что данные не потеряются (volume `postgres_data`).

### 1.2 Обновление зависимостей `rest_service`
- [x] Добавить `pgvector` в `pyproject.toml`.
- [x] Обновить `alembic` и `sqlalchemy` если нужно.

### 1.3 Модель `Memory`
Создать новую модель в `shared_models` (и таблицу в `rest_service`):

```python
class Memory(BaseModel, table=True):
    """Unified memory entity for user/assistant context."""
    
    __tablename__ = "memories"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    assistant_id: UUID | None = Field(
        default=None, 
        foreign_key="assistant.id", 
        index=True,
        description="None = shared across all assistants"
    )
    
    # Content
    text: str = Field(sa_column=Column(TEXT), description="What to remember")
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(1536)),  # text-embedding-3-small
        description="Vector representation for semantic search"
    )
    
    # Classification
    memory_type: str = Field(
        index=True,
        description="user_fact | conversation_insight | preference | event | extracted_knowledge"
    )
    
    # Metadata
    source_message_id: UUID | None = Field(default=None, description="Link to origin message")
    importance: int = Field(default=1, description="1-10 scale for retention policy")
    last_accessed_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 1.4 Индексы
- [x] Добавить HNSW индекс для поля `embedding` в миграции Alembic:
  ```python
  op.create_index(
      'ix_memories_embedding',
      'memories',
      ['embedding'],
      postgresql_using='hnsw',
      postgresql_with={'m': 16, 'ef_construction': 64},
      postgresql_ops={'embedding': 'vector_cosine_ops'}
  )
  ```

---

## Этап 2: API в REST Service

### 2.1 CRUD Endpoints
- [x] `POST /memories` — создание (принимает text, делает embedding НЕ здесь, а принимает готовый или оставляет null?) 
    *   *Уточнение:* REST сервис тупой. Он принимает `embedding` как список float. Эмбеддинг генерирует тот, кто вызывает (RAG или Assistant).
- [x] `GET /memories/{id}`
- [x] `PATCH /memories/{id}`
- [x] `DELETE /memories/{id}`
- [x] `GET /memories/user/{user_id}` — списочный метод с фильтрами.

### 2.2 Search Endpoint
- [x] `POST /memories/search`
    - Input: `{ "embedding": [0.1, ...], "limit": 10, "threshold": 0.7, "user_id": 123 }`
    - Logic: SQL query с оператором `<=>` (cosine distance).
    - Output: List of Memories with `score`.

---

## Этап 3: Интеграция в RAG Service

### 3.1 Клиент к REST Service
- [x] Обновить клиент в `rag_service` для работы с новыми эндпоинтами `memories`.

### 3.2 Логика поиска
- [x] Реализовать метод `search_relevant_memories(query: str, user_id: int)`:
    1. Получить embedding для `query` (OpenAI).
    2. Вызвать `rest_service.search_memories(embedding, user_id)`.
    3. Вернуть результат.

---

## Этап 4: Интеграция в Assistant Service

### 4.1 Memory Tool
- [ ] Создать `MemoryTool` (или обновить существующий), который ходит в `rag_service` (или напрямую в REST для простых операций?).
    *   *Решение:* Для поиска идем в `rag_service`. Для простого сохранения (без поиска) можно идти в `rest_service`, но лучше все через RAG, чтобы он мог сразу генерить эмбеддинг при сохранении.

### 4.2 Graph Node
- [ ] Добавить узел `retrieve_memories` в граф диалога.
- [ ] Вызывать поиск перед генерацией ответа.
- [ ] Добавлять найденные факты в System Prompt.

---

## Этап 5: Миграция и Зачистка

### 5.1 Удаление старого
- [x] Удалить модели `UserFact` и `UserSummary`.
- [x] Удалить соответствующие таблицы в БД.
- **Важно:** Миграция данных не требуется (проект в разработке), просто дропаем старые таблицы.

### 5.2 Cleanup
- [x] Удалить старый код, связанный с Qdrant (если он полностью заменяется) или перенастроить `rag_service` на использование только Postgres.
    *   *Уточнение:* Qdrant полностью выпиливаем из инфраструктуры.

---

## Приоритеты реализации

### MVP (День 1-2)
1. Обновление Docker Compose (pgvector).
2. Модель `Memory` и миграции.
3. Базовый CRUD + Search в `rest_service`.

### Integration (День 2-3)
4. Логика в `rag_service` (embedding generation).
5. Подключение `assistant_service` к новому API.

### Cleanup (День 3)
6. Удаление Qdrant и старых таблиц.

---

## Метрики успеха
- [x] `docker-compose up` поднимает базу с pgvector без ошибок.
- [ ] Векторный поиск по 1000+ записям работает < 100ms.
- [ ] Ассистент "помнит" факты, сказанные 50 сообщений назад.
