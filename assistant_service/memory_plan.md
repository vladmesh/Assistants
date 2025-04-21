---
title: План реализации Memory Pipeline для LangGraphAssistant
---

## 📦 Итоговая структура проекта (Актуализировано)

```
assistant_service/
├─ src/
│  ├─ assistants/
│  │  ├─ langgraph/
│  │  │  ├─ graph_builder.py           # сборка графа для LangGraphAssistant (✅)
│  │  │  ├─ langgraph_assistant.py     # сам класс LangGraphAssistant и определение AssistantState (✅)
│  │  │  ├─ state.py                   # определение AssistantState (✅)
│  │  │  ├─ nodes/
│  │  │  │  ├─ init_state.py           # узел: инициализация базового состояния (системный промпт) (✅)
│  │  │  │  ├─ entry_check_facts.py    # узел: решает, нужно ли обновить факты, и вызывает API (✅)
│  │  │  │  ├─ load_user_facts.py      # узел: форматирует факты из state в сообщение (✅)
│  │  │  │  ├─ update_state_after_tool.py # узел: обновляет флаги после вызова инструмента (✅)
│  │  │  │  └─ summarize_history.py    # узел: суммаризует историю (⏳ TODO)
│  │  │  └─ utils/
│  │  │     ├─ token_counter.py        # считает токены (✅)
│  │  │     └─ ...
│  └─ tools/                          # Инструменты, вызываемые графом
│     └─ user_fact_tool.py           # Инструмент для *сохранения* фактов (вызывает POST/PATCH API) (✅)
│  └─ ...
└─ tests/
   ├─ assistants/
   │  ├─ langgraph/
   │  │  ├─ test_graph_builder.py   # Тест на базовую сборку графа (✅)
   │  │  └─ ... (тесты узлов ⏳ TODO)
   │  ├─ test_langgraph_assistant.py # Закомментированные тесты (требуют исправления)
   ├─ test_memory_pipeline_e2e.py     # (⏳ TODO)
   └─ ...
```

## 📝 Определение состояния (AssistantState) (Актуализировано)

- `AssistantState` (определяется как `TypedDict` в `state.py`)
  - `messages: Annotated[Sequence[BaseMessage], operator.add]` (✅)
  - `pending_facts: list[str]` # Факты, полученные от API, готовые к добавлению в messages (✅)
  - `facts_loaded: bool` # Был ли узел load_user_facts выполнен в этом цикле (✅)
  - `last_summary_ts: Optional[datetime]` (⏳ для Итерации 4)
  - `llm_context_size: int` # Устанавливается при инициализации ассистента (✅)
  - `fact_added_in_last_run: bool` # Флаг, указывающий, был ли добавлен факт в последнем запуске (✅)
  - `current_token_count: Optional[int]` # Кешированное количество токенов (✅)
  - `user_id: str` # ID пользователя, необходим для вызова API фактов (✅)
  - `log_extra: Dict[str, Any]` # Дополнительная информация для логирования (опционально) (✅)
  - `dialog_state: List[str]` # Стек состояний диалога (опционально, для отладки) (✅)
  - `triggered_event: Optional[Dict]` # Событие, вызвавшее запуск графа (✅)

## 📖 Общие рекомендации (Без изменений)

- **Документация узлов:** В начале каждого файла узла (`nodes/*.py`) рекомендуется добавлять docstring, описывающий:
    - Назначение узла.
    - Входные поля `state`, которые он читает.
    - Поля `state`, которые он обновляет.
    - Возможные побочные эффекты.
- **Инициализация `llm_context_size` и `user_id`:** Рекомендуется устанавливать эти поля один раз при создании экземпляра графа (например, через `initial_state_template` или при вызове `ainvoke`), а не передавать их при каждом вызове узлов.
- **Подсчет токенов:** Для оптимизации рекомендуется кэшировать количество токенов в `current_token_count`. Этот счетчик должен обновляться в узлах, которые изменяют список `messages` (`load_user_facts`, `summarize_history`), а также **в основном узле ассистента (`_run_assistant_node`)** после добавления ответа LLM.

## 🔄 Итерации

### Итерация 1. Перенос базовой сборки графа (✅ Готово)
- Создан `graph_builder.py`.
- Базовый ReAct-граф собирается в `build_full_graph()`.
- Тест `tests/assistants/langgraph/test_graph_builder.py` подтверждает сборку.

### Итерация 2. Узел проверки и обновления фактов (`entry_check_facts`) (✅ Готово)
- **Цель:** В начале каждого цикла проверять, нужно ли обновить факты пользователя, и если да, вызывать GET API.
- **Компоненты:**
    - **Узел `entry_check_facts_node`:** (`nodes/entry_check_facts.py`)
        - **Реализация:** Использует `RestServiceClient` (переданный при сборке графа) для вызова `rest_client.get_user_facts(user_id=user_id)`.
        - **Зависимости:** Требует `rest_client` и `user_id` из `state`.
        - **Логика:** Проверяет флаги `facts_loaded` и `fact_added_in_last_run`. Если нужно обновить, вызывает API.
        - **Выход:** Обновляет `pending_facts` и сбрасывает `fact_added_in_last_run = False`.
        - **Пример кода узла:**
```python
# nodes/entry_check_facts.py
# ... импорты ...
async def entry_check_facts_node(state: AssistantState, rest_client: RestServiceClient) -> Dict[str, Any]:
    user_id = state.get("user_id")
    # ... проверка user_id ...
    should_refresh = not state.get("facts_loaded", False) or state.get("fact_added_in_last_run", False)
    if should_refresh:
        try:
            retrieved_facts = await rest_client.get_user_facts(user_id=user_id)
            return {"pending_facts": retrieved_facts if isinstance(retrieved_facts, list) else [], "fact_added_in_last_run": False}
        except Exception as e:
            logger.exception(...)
            return {"pending_facts": [], "fact_added_in_last_run": False}
    else:
        return {"pending_facts": [], "fact_added_in_last_run": False}
```
- **Интеграция в граф (`build_full_graph`):** Узел добавлен, `rest_client` передается через `functools.partial`. Ребро `init_state` -> `check_facts`.
- **Триггер обновления:** Флаг `fact_added_in_last_run` устанавливается узлом `update_state_after_tool_node` (см. Итерацию 3.1).
- **Тест:** Модульный тест узла (⏳ TODO).

### Итерация 3. Форматирование фактов (`load_user_facts`) (✅ Готово)
- Файл: `nodes/load_user_facts.py`.
- **Задача:** Взять факты из `state["pending_facts"]` и добавить их как `SystemMessage` (с `name="user_facts"`) в `state["messages"]`, обновив `current_token_count`.
- **Реализация:** Узел существует и выполняет задачу. Корректно обрабатывает наличие/отсутствие `pending_facts`, заменяет старое сообщение с фактами, вставляет новое после системного промпта (если есть), вызывает `count_tokens` и обновляет `current_token_count`, устанавливает `facts_loaded = True`.
- **Интеграция в граф:** Ребро `check_facts` -> `load_facts`.
- **Тест:** Модульный тест узла (⏳ TODO).

### Итерация 3.1. Обработка результата сохранения факта (`update_state_after_tool_node`) (✅ Готово)
- Файл: `nodes/update_state_after_tool.py`.
- **Задача:** После выполнения инструмента проверить, был ли это успешный вызов `UserFactTool` (с именем `"save_user_fact"`). Если да, установить флаг `fact_added_in_last_run = True`, чтобы инициировать обновление фактов на следующем шаге.
- **Реализация:** Узел существует. Проверяет последнее сообщение: если это `ToolMessage` с именем `"save_user_fact"` и контентом `"Факт успешно добавлен."`, то возвращает `{"fact_added_in_last_run": True}`.
- **Интеграция в граф:** Ребро `tools` -> `update_state_after_tool`. Ребро `update_state_after_tool` -> `assistant`.
- **Тест:** Модульный тест узла (⏳ TODO).

### Итерация 4. Узел `summarize_history` (⏳ Не начато)
- Файл: `nodes/summarize_history.py` (создать).
- **Задача:** Сокращать историю сообщений, если она превышает порог (например, 60% от `llm_context_size`).
- **Логика:**
    - Получить `messages`, `current_token_count`, `llm_context_size` из state.
    - Если `current_token_count / llm_context_size >= 0.6`:
        - Определить `head` (старые сообщения для суммаризации) и `tail` (недавние сообщения для сохранения).
        - Вызвать `summary_llm` (отдельная LLM, передаваемая при сборке графа) с `head` для получения краткого содержания (`summary_content`).
        - Создать `summary_message = SystemMessage(content=summary_content, name="history_summary")`.
        - Сформировать `new_messages = [summary_message] + tail`.
        - Пересчитать `new_token_count = count_tokens(new_messages)`.
        - Вернуть `{ "messages": new_messages, "last_summary_ts": datetime.utcnow(), "current_token_count": new_token_count }`.
    - Иначе: вернуть `{}`.
- **Зависимости:** Требует `summary_llm` (инстанс LLM), `llm_context_size`, `current_token_count` из `state`.
- **Интеграция в граф:** Потребуется условное ребро после `load_facts` (см. Итерацию 5).
- **Тест:** Модульный тест узла (⏳ TODO).

### Итерация 5. Объединение в `build_full_graph` (🔄 Частично готово)
- Файл: `graph_builder.py`.
- **Текущая структура:** `START -> init_state -> check_facts -> load_facts -> assistant -> tools -> update_state_after_tool -> assistant / END`.
- **Задача:** Интегрировать узел `summarize` и условное ветвление.
- **План изменений:**
    - Добавить узел `summarize` (`nodes/summarize_history.py`).
    - Добавить `summary_llm` как аргумент в `build_full_graph`.
    - Изменить рёбра после `load_facts`:
        - Добавить условное ребро (`add_conditional_edges`) от `load_facts` к `summarize` (если `should_summarize(state)` -> `True`) или к `assistant` (если `False`).
        - Добавить ребро от `summarize` к `assistant`.
    - **Пример целевой структуры (с суммаризацией):**
```python
# graph_builder.py
# ... (импорты, включая should_summarize)

def build_full_graph(
    run_node_fn, 
    tools: list[BaseTool], 
    checkpointer, 
    rest_client: RestServiceClient, 
    system_prompt_text: str, 
    summary_llm: BaseChatModel # Добавить LLM для суммаризации
):
    builder = StateGraph(AssistantState)

    # --- Узлы ---
    # init_state
    bound_init_node = functools.partial(init_state_node, system_prompt_text=system_prompt_text)
    builder.add_node("init_state", bound_init_node)
    # check_facts
    bound_entry_node = functools.partial(entry_check_facts_node, rest_client=rest_client)
    builder.add_node("check_facts", bound_entry_node)
    # load_facts
    builder.add_node("load_facts", load_user_facts_node)
    # summarize (НОВЫЙ)
    bound_summarize_node = functools.partial(summarize_history_node, summary_llm=summary_llm)
    builder.add_node("summarize", bound_summarize_node)
    # assistant
    builder.add_node("assistant", run_node_fn)
    # tools
    agent_tools = tools # Передаем все инструменты, которые агент может вызывать
    builder.add_node("tools", ToolNode(tools=agent_tools))
    # update_state_after_tool
    builder.add_node("update_state_after_tool", update_state_after_tool_node)

    # --- Рёбра ---
    builder.add_edge(START, "init_state")
    builder.add_edge("init_state", "check_facts")
    builder.add_edge("check_facts", "load_facts")

    # УСЛОВНОЕ РЕБРО для суммаризации (НОВОЕ)
    builder.add_conditional_edges(
        "load_facts",
        should_summarize, # Функция, проверяющая state["current_token_count"] / state["llm_context_size"]
        {
            "summarize": "summarize", # Идти на суммаризацию
            "assistant": "assistant", # Идти сразу к ассистенту
        }
    )
    # Ребро после суммаризации (НОВОЕ)
    builder.add_edge("summarize", "assistant")

    # Цикл агент-инструменты
    builder.add_conditional_edges(
        "assistant",
        tools_condition, # Встроенное условие LangGraph
        {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "update_state_after_tool")
    builder.add_edge("update_state_after_tool", "assistant")

    return builder.compile(checkpointer=checkpointer)
```
- **Тест:** Обновить `test_build_full_graph_compiles` для проверки новой структуры (когда будет реализована).

### Итерация 6. End-to-end тесты (⏳ Не начато)
- Файл `tests/test_memory_pipeline_e2e.py` (создать/обновить).
- **Целевые тесты:**
    - Проверка вызова `rest_client.get_user_facts` узлом `entry_check_facts` при первом запуске (`facts_loaded=False`).
    - Проверка *не* вызова `get_user_facts` при `fact_added_in_last_run=False` и `facts_loaded=True`.
    - Проверка вызова `get_user_facts` при `fact_added_in_last_run=True`.
    - Проверка корректной вставки/замены `SystemMessage` с фактами узлом `load_facts`.
    - Проверка корректной установки флага `fact_added_in_last_run=True` узлом `update_state_after_tool` после успешного вызова `"save_user_fact"`.
    - Проверка обновления `current_token_count` в узлах `load_facts`, `summarize_history` (когда будет), `assistant`.
    - **Тест:** Пограничный случай `token_count / llm_context_size == 0.6` -> переход к `summarize` (когда будет).
    - **Тест:** Случай ошибки при вызове `get_user_facts` -> граф продолжает работу без фактов.
    - **Тест:** Полный цикл с суммаризацией (когда будет).
- **Примечание:** Закомментированные тесты в `test_langgraph_assistant.py` требуют отдельного анализа и исправления.

