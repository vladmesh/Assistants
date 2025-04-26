# План Доработки: Динамическое Формирование Промпта и Управление Состоянием

**Цель:** Перенести хранение `summary` и `facts` из состояния графа (`AssistantState`) в базу данных (`rest_service`), управляя ими через экземпляр `LangGraphAssistant`. В состоянии графа оставить только "чистую" историю сообщений (`HumanMessage`, `AIMessage`, `ToolMessage`). Узел `assistant` будет динамически генерировать единственный `SystemMessage` перед каждым вызовом LLM.

---

## ✅ Фаза 1: Модификации `rest_service` (Уточненная)

### ✅ 1.1 Модель Базы Данных (`rest_service/src/models/`)

*   ✅ **Создать модель `UserSummary`:**
    *   Файл: `rest_service/src/models/user_summary.py` (новый).
    *   Класс `UserSummary(BaseModel, table=True)`:
        *   `id: UUID = Field(default_factory=uuid4, primary_key=True)`
        *   `user_id: int = Field(foreign_key="telegramuser.id", index=True)`
        *   `secretary_id: UUID = Field(foreign_key="assistant.id", index=True)`
        *   `summary_text: str = Field(sa_column=Column(TEXT)) # Используем TEXT для длинных саммари`
        *   `created_at: datetime = Field(default_factory=datetime.now)`
        *   `updated_at: datetime = Field(default_factory=datetime.now)`
        *   `__tablename__ = "user_summaries"`
        *   Добавить уникальный индекс на `(user_id, secretary_id)`.
*   ✅ **Связи:**
    *   В `models/user.py` (`TelegramUser`): `summaries: List["UserSummary"] = Relationship(back_populates="user")`.
    *   В `models/assistant.py` (`Assistant`): `user_summaries: List["UserSummary"] = Relationship(back_populates="secretary")`.
*   ✅ **Модель Фактов (`UserFact`):**
    *   **Проверить:** Модель `UserFact` (вероятно в `models/user_fact.py`) и её связи уже должны существовать, так как есть API и схемы для фактов. Убедиться, что она содержит поля `id`, `user_id`, `fact` (или `fact_text`), `created_at`, `updated_at`. (Проверено).
*   ✅ **Миграция Alembic:**
    *   Создать новую миграцию (`./manage.py migrate "Add user_summaries table"`) для добавления таблицы `user_summaries`. (Таблица для фактов уже должна существовать). (Создана).

### ✅ 1.2 CRUD Операции (`rest_service/src/crud/`)

*   ✅ **Создать `crud/user_summary.py`:**
    *   `create_or_update_summary(db: AsyncSession, user_id: int, secretary_id: UUID, summary_text: str) -> UserSummary`: Находит или создает запись, обновляет текст и `updated_at`.
    *   `get_summary(db: AsyncSession, user_id: int, secretary_id: UUID) -> Optional[UserSummary]`: Ищет последнюю запись по `user_id` и `secretary_id`.
    *   Добавить импорт `import crud.user_summary` в `crud/__init__.py`.
*   ✅ **Проверить `crud/user_fact.py`:**
    *   Убедиться, что файл существует и содержит функции `get_user_facts_by_user_id` и `create_user_fact`. (Проверено).

### ✅ 1.3 API Эндпоинты (`rest_service/src/routers/`)

*   ✅ **Создать `routers/user_summaries.py`:**
    *   `GET /api/user-summaries/{user_id}/{secretary_id}` (Dependency: `get_session`, Response Model: `Optional[UserSummaryRead]`).
    *   `POST /api/user-summaries/{user_id}/{secretary_id}` (Dependency: `get_session`, Request Body: `UserSummaryCreateUpdate`, Response Model: `UserSummaryRead`).
*   ✅ **Проверить `routers/user_facts.py`:**
    *   Убедиться, что эндпоинты `GET /users/{user_id}/facts` и `POST /users/{user_id}/facts` существуют и работают корректно. (Проверено).
*   ✅ **Регистрация Роутеров:**
    *   Добавить роутер `user_summaries` в `rest_service/src/main.py`. (Роутер для фактов уже должен быть зарегистрирован).

### ✅ 1.4 API Схемы (`shared_models/src/shared_models/api_schemas/`)

*   ✅ **Создать `user_summary.py`:**
    *   `UserSummaryRead(BaseSchema, TimestampSchema)`: `summary_text: str`, `updated_at: datetime`.
    *   `UserSummaryCreateUpdate(BaseSchema)`: `summary_text: str`.
*   ✅ **Проверить `user_fact.py`:**
    *   Убедиться, что схемы `UserFactRead` и `UserFactCreate` существуют и соответствуют используемой модели `UserFact`. (Проверено).

---

## Фаза 2: Модификации `assistant_service`

### 2.1 Состояние Графа (`assistants/langgraph/state.py`)

*   В `AssistantState` удалить поле `last_summary_ts: Optional[datetime]`.
*   Поле `dialog_state` оставить, если оно используется, иначе удалить.

### 2.2 Редьюсер Сообщений (`assistants/langgraph/reducers.py`)

*   В функции `custom_message_reducer`:
    *   Внутри `_filter_system_messages_and_get_summary`:
        *   Удалить переменную `first_history_summary`.
        *   Удалить логику проверки `msg_name == HISTORY_SUMMARY_NAME`.
        *   Функция теперь должна возвращать только `List[BaseMessage]` (отфильтрованный список).
    *   В основной функции `custom_message_reducer`:
        *   Изменить вызов: `potentially_valid_messages = _filter_system_messages(combined_messages)`.
        *   Удалить шаг 5 ("Prepend the first history summary").
        *   Убедиться, что функция корректно обрабатывает `None` на входе и возвращает `List[BaseMessage]`.

### 2.3 Класс Ассистента (`assistants/langgraph/langgraph_assistant.py`)

*   **Поля класса:**
    *   Добавить:
        ```python
        self.summary: Optional[str] = None
        self.facts: Optional[List[str]] = None
        self.system_prompt_template: str = "" # Будет заполнено в __init__
        self.needs_summary_refresh: bool = True
        ```
    *   Инициализировать `self.system_prompt_template = self.config["system_prompt"]` в `__init__`.
*   **Метод `_load_initial_data`:**
    *   Создать асинхронный метод `async def _load_initial_data(self):`.
    *   Реализовать логику запросов к `rest_client.get_user_summary(self.user_id, self.assistant_id)` и `rest_client.get_user_facts(self.user_id)`.
    *   Сохранять результаты в `self.summary` и `self.facts`.
    *   Устанавливать `self.needs_summary_refresh = False` и `self.needs_fact_refresh = False` при успехе.
    *   Обработать ошибки (логгировать и оставлять поля `None`, флаги `True`).
*   **Метод `_add_system_prompt_modifier`:**
    *   **Важно:** Этот метод **должен** по-прежнему возвращать `List[BaseMessage]`.
    *   **Логика внутри:**
        1.  Проверить флаги `needs_summary_refresh`/`needs_fact_refresh`. Если `True`, асинхронно вызвать `self.rest_client.get_user_summary/get_user_facts` для обновления `self.summary`/`self.facts` и сбросить флаги.
        2.  Сформатировать `self.system_prompt_template`, подставляя `self.summary` и `self.facts` (например, `facts_str = "\n".join(self.facts or [])`). Обработать случаи, когда `summary` или `facts` равны `None`.
        3.  Создать **один** `SystemMessage(content=formatted_prompt_text)`. **Не присваивать ему `name`**.
        4.  Получить `current_messages = state.get("messages", [])`.
        5.  **Отфильтровать** `current_messages`, оставив только `HumanMessage`, `AIMessage`, `ToolMessage`.
        6.  Вернуть `[новый_SystemMessage] + отфильтрованная_история`.
*   **Метод `_run_assistant_node`:**
    *   Оставить вызов `self.agent_runnable.ainvoke(state)` без изменений. Метод `_add_system_prompt_modifier` будет вызван неявно через `agent_runnable`.
    *   Сохранить логику установки `self.needs_fact_refresh = True` при ответе от `FACT_SAVE_TOOL_NAME`.

### 2.4 Фабрика Ассистентов (`assistants/factory.py`)

*   В методе `get_assistant_by_id`:
    *   После строки `instance = LangGraphAssistant(...)` добавить вызов `await instance._load_initial_data()`.

### 2.5 Узел Суммаризации (`assistants/langgraph/nodes/summarize_history.py`)

*   **Передача зависимостей:**
    *   В `graph_builder.py` при добавлении узла `summarize` использовать `functools.partial`, чтобы передать в `summarize_history_node` не только `summary_llm`, но и `rest_client=self.rest_client` (из `LangGraphAssistant`).
    *   Модифицировать сигнатуру `summarize_history_node`, чтобы она принимала `rest_client: RestServiceClient`. Также узлу понадобится `user_id` и `assistant_id` (получить из `state`).
*   **Модификация `summarize_history_node`:**
    *   После строки `new_summary = response` (где получен результат от `summary_llm`):
        *   Вызвать `await rest_client.create_or_update_user_summary(state["user_id"], assistant_id, new_summary)` (нужно определить `assistant_id` текущего секретаря, возможно, он тоже есть в `state` или его нужно передать).
        *   **Важно:** Убрать создание и возврат `SystemMessage(name=HISTORY_SUMMARY_NAME, content=new_summary)`.
        *   Узел должен возвращать `{"messages": initial_deletes}`.

---

## Фаза 3: Админка

*   Добавить раздел/поле для просмотра `UserSummary.summary_text`.
*   Реализовать запрос к `rest_service` (`GET /api/user-summaries/{user_id}/{secretary_id}`) для получения данных.

---

## Фаза 4: Тестирование

*    **Unit-тесты:**
    *✅ Для новых/измененных CRUD и API в `rest_service`. (Выполнено)
    *   Для `_load_initial_data`, `_add_system_prompt_modifier` в `LangGraphAssistant`.
    *   Для `custom_message_reducer` (проверить фильтрацию `SystemMessage` и отсутствие логики `HISTORY_SUMMARY_NAME`).
    *   Для `summarize_history_node` (проверить вызов `rest_client` и корректный возврат `RemoveMessage`).
*   **Интеграционные тесты:**
    *   Проверить полный цикл: вызов ассистента -> `_load_initial_data` -> `_add_system_prompt_modifier` -> вызов LLM.
    *   Проверить цикл суммаризации: накопление истории -> вызов `summarize_history_node` -> сохранение саммари через `rest_service` -> удаление сообщений из state -> последующий вызов LLM с обновленным саммари в промпте.
    *   Проверить обновление фактов и их отражение в промпте.
    *   (Тесты API и CRUD для rest_service выполнены)

---

**Ключевые моменты реализации:**

*   ✅ Начинать с изменений в `rest_service` (модели, CRUD, API). (Выполнено)
*   Затем модифицировать `assistant_service`, тестируя компоненты по мере их изменения.
*   Особое внимание уделить корректной передаче `user_id`, `assistant_id` и `rest_client` в `summarize_history_node`.
*   Тщательно протестировать логику кэширования/обновления `summary` и `facts` в `LangGraphAssistant`. 