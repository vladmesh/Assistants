## 📦 Итоговая структура проекта

```
assistant_service/
├─ src/
│  ├─ assistants/
│  │  ├─ langgraph/
│  │  │  ├─ graph_builder.py           # сборка графа для LangGraphAssistant
│  │  │  ├─ langgraph_assistant.py     # сам класс LangGraphAssistant и определение AssistantState
│  │  │  ├─ nodes/
│  │  │  │  ├─ entry_check_facts.py    # узел: решает, нужно ли обновить факты, и вызывает API
│  │  │  │  ├─ load_user_facts.py      # узел: форматирует факты из state в сообщение
│  │  │  │  ├─ summarize_history.py    # узел: суммаризует историю
│  │  │  │  └─ ...                     # будущие узлы
│  │  │  └─ utils/
│  │  │     ├─ token_counter.py        # считает токены
│  │  │     └─ ...                     
│  │  └─ tools/                        # Инструменты, вызываемые графом
│  │     └─ get_facts_tool.py         # Инструмент для вызова GET /api/users/{user_id}/facts
│  └─ ...
└─ tests/
   ├─ test_entry_check_facts.py
   ├─ test_load_user_facts.py
   ├─ test_summarize_history.py
   ├─ test_memory_pipeline_e2e.py
   └─ ...
```

## 📝 Определение состояния (AssistantState)

- `AssistantState` (определяется как `TypedDict` в `langgraph_assistant.py` или отдельном модуле)
  - `messages: Annotated[Sequence[BaseMessage], operator.add]`
  - `pending_facts: list[str]` # Факты, полученные от API, готовые к добавлению в messages
  - `facts_loaded: bool` # Был ли узел load_user_facts выполнен в этом цикле
  - `last_summary_ts: Optional[datetime]`
  - `llm_context_size: int` # Устанавливается при инициализации ассистента
  - `fact_added_in_last_run: bool` # Флаг, указывающий, был ли добавлен факт в последнем запуске
  - `current_token_count: Optional[int]` # Кешированное количество токенов
  - `user_id: str` # ID пользователя, необходим для вызова GetFactsTool

## 📖 Общие рекомендации

- **Документация узлов:** В начале каждого файла узла (`nodes/*.py`) рекомендуется добавлять docstring, описывающий:
    - Назначение узла.
    - Входные поля `state`, которые он читает.
    - Поля `state`, которые он обновляет.
    - Возможные побочные эффекты.
- **Инициализация `llm_context_size`:** Рекомендуется устанавливать это поле один раз при создании экземпляра графа (например, через `initial_state_template` в конструкторе `LangGraphAssistant`), а не передавать его при каждом вызове.
- **Подсчет токенов:** Для оптимизации рекомендуется кэшировать количество токенов в `current_token_count`. Этот счетчик должен обновляться в узлах, которые изменяют список `messages` (`load_user_facts`, `summarize_history`), а также **в основном узле ассистента (`run_node_fn`)** после добавления ответа LLM.

## 🔄 Итерации

### Итерация 1. Перенос базовой сборки графа
- Создать `graph_builder.py`.
- Вынести базовый ReAct-граф в `build_base_graph()`.
- Тест `tests/test_graph_builder.py`.

### Итерация 2. Узел проверки и обновления фактов (`entry_check_facts`)
- **Цель:** В начале каждого цикла проверять, нужно ли обновить факты пользователя, и если да, вызывать GET API.
- **Компоненты:**
    - **Инструмент `GetFactsTool`:** (`tools/get_facts_tool.py`, вызывает GET API, возвращает `list[str]`).
    - **Узел `entry_check_facts_node`:**
        - Файл: `nodes/entry_check_facts.py`.
        - **Зависимости:** Должен иметь доступ к вызову `GetFactsTool` (например, через `functools.partial`).
        - **Логика:**
```python
# nodes/entry_check_facts.py
import logging # Рекомендуется использовать logging
from functools import partial
# ... другие импорты

logger = logging.getLogger(__name__)

async def entry_check_facts_node(state: AssistantState, get_facts_tool_func: callable) -> dict:
    """Checks if facts need refreshing (first run or after adding a fact) 
       and calls the GetFactsTool if needed.
    """
    # Обновляем факты, если это первый запуск (facts_loaded=False) ИЛИ если факт был добавлен в прошлом цикле
    should_refresh = not state.get("facts_loaded", False) or state.get("fact_added_in_last_run", False)
    # TODO: Добавить другие условия (например, TTL)
    
    if should_refresh:
        logger.info("Refreshing user facts.")
        try:
            retrieved_facts = await get_facts_tool_func()
            logger.debug(f"Successfully fetched {len(retrieved_facts)} facts.")
            return { 
                "pending_facts": retrieved_facts if isinstance(retrieved_facts, list) else [], 
                "fact_added_in_last_run": False # Сбрасываем флаг
            }
        except Exception as e:
            logger.error(f"Error fetching facts: {e}", exc_info=True)
            # Можно добавить механизм retry или просто продолжить без фактов
            return { "pending_facts": [], "fact_added_in_last_run": False }
    else:
        # Обновление не требуется
        return { "pending_facts": [], "fact_added_in_last_run": False }
```
- **Интеграция в граф (`build_full_graph`):**
```python
get_facts_tool = next((t for t in tools if t.name == "get_facts_tool"), None)
if not get_facts_tool:
    raise ValueError("GetFactsTool is required but not found in provided tools.")

# Важно: Убедиться, что get_facts_tool._execute корректно получает user_id
# из state или своего внутреннего контекста
bound_entry_node = partial(entry_check_facts_node, get_facts_tool_func=get_facts_tool._execute)

builder.add_node("check_facts", bound_entry_node)
builder.add_edge(START, "check_facts")

builder.add_node("load_facts", load_user_facts_node)
builder.add_edge("check_facts", "load_facts") 
```
- **Обновление `assistant`:** Узел `assistant` (`run_node_fn`) устанавливает `fact_added_in_last_run = True` после успешного *сохранения* факта через `UserFactTool`.
- **Важно:** Убедиться, что `user_id` доступен в `AssistantState` (рекомендуется устанавливать через `initial_state_template`) и корректно используется `GetFactsTool`.
- Тест `tests/test_entry_check_facts.py`.

### Итерация 3. Форматирование фактов (`load_user_facts`)
- Файл: `nodes/load_user_facts.py`.
- **Задача:** Взять факты из `state["pending_facts"]` и добавить их как `SystemMessage` в `state["messages"]`, обновив `current_token_count`.
- **Код узла:**
```python
# nodes/load_user_facts.py
async def load_user_facts_node(state: AssistantState) -> dict:
    """Formats facts from pending_facts into a SystemMessage and adds/replaces it in messages."""
    pending_facts = state.get("pending_facts", [])
    if not pending_facts:
        # Если факты не обновились, просто возвращаем текущий token_count (если он есть)
        return {"facts_loaded": False, "current_token_count": state.get("current_token_count")} 
    
    msg_content = "Current user facts:\n" + "\\n".join(f"- {f}" for f in pending_facts)
    msg = SystemMessage(content=msg_content, name="user_facts")
    
    current_messages = state.get("messages", [])
    # Удаляем старое сообщение с фактами, если оно было
    updated_messages = [m for m in current_messages if getattr(m, 'name', None) != 'user_facts']
    # Вставляем актуальные факты в начало (или после первого системного сообщения, если оно есть)
    updated_messages.insert(0, msg) 
    
    new_token_count = count_tokens(updated_messages)
    return {
        "messages": updated_messages,
        "pending_facts": [], 
        "facts_loaded": True, 
        "current_token_count": new_token_count
    }
```
- **Интеграция в граф:** Ребро от `check_facts` к `load_facts` добавлено.
- Тест `tests/test_load_user_facts.py`.

### Итерация 4. Узел `summarize_history`
- Файл: `nodes/summarize_history.py`.
- Использует `state["current_token_count"]` и `state["llm_context_size"]`.
- **Код узла:**
```python
# nodes/summarize_history.py
async def summarize_history_node(state: AssistantState) -> dict:
    # ... (получение msgs, max_tokens, token_count)
    
    # Проверяем наличие необходимых данных в state
    token_count = state.get("current_token_count")
    max_tokens = state.get("llm_context_size")
    if token_count is None or max_tokens is None:
         logger.warning("Missing token_count or max_tokens in state, skipping summarization.")
         return {} # Не можем работать без данных

    if token_count / max_tokens < 0.6:
        return {} # Контекст недостаточно заполнен

    # ... (логика head, tail, вызов summary_llm -> summary_message)
    num_messages_to_keep = 3
    head, tail = msgs[:-num_messages_to_keep], msgs[-num_messages_to_keep:]
    # ... (вызов LLM для получения ai_response.content)
    summary_content = "History summary (...):\\n" + ai_response.content
    summary_message = SystemMessage(content=summary_content)

    new_messages = [summary_message] + tail
    new_token_count = count_tokens(new_messages)
    return {
        "messages": new_messages,
        "last_summary_ts": datetime.utcnow(),
        "current_token_count": new_token_count
    }
```
- **Интеграция в граф:** (Внимание на явное добавление ребра `load_facts` -> `assistant`)
```python
builder.add_node("summarize", summarize_history_node)

# Определяем функцию-условие
def should_summarize(state: AssistantState):
    token_count = state.get("current_token_count")
    max_tokens = state.get("llm_context_size")
    if token_count is None or max_tokens is None:
        return "assistant" # Не можем решить, идем к ассистенту
    if token_count / max_tokens >= 0.6:
        return "summarize"
    else:
        return "assistant"

# Используем conditional_edges с функцией, возвращающей имя узла
builder.add_conditional_edges(
    "load_facts", 
    should_summarize, 
    {
        "summarize": "summarize",
        "assistant": "assistant", # Явно указываем путь для False
    }
)

# Добавляем ребро после суммаризации
builder.add_edge("summarize", "assistant")
```
- Тест `tests/test_summarize_history.py`.

### Итерация 5. Объединение в `build_full_graph`
- Файл: `graph_builder.py`.
- Функция `build_full_graph` собирает узлы и рёбра, включая явное ветвление после `load_facts`.
```python
# graph_builder.py
# ... (импорты, включая should_summarize из предыдущей итерации)

def build_full_graph(run_node_fn, tools: list[BaseTool], checkpointer):
    builder = StateGraph(AssistantState)

    get_facts_tool = next((t for t in tools if t.name == "get_facts_tool"), None)
    if not get_facts_tool:
        raise ValueError("GetFactsTool (get_facts_tool) is required but not found.")
    
    bound_entry_node = partial(entry_check_facts_node, get_facts_tool_func=get_facts_tool._execute)
    builder.add_node("check_facts", bound_entry_node)
    builder.add_edge(START, "check_facts")

    builder.add_node("load_facts", load_user_facts_node)
    builder.add_edge("check_facts", "load_facts")

    builder.add_node("summarize", summarize_history_node)
    builder.add_conditional_edges(
        "load_facts",
        should_summarize,
        {"summarize": "summarize", "assistant": "assistant"},
    )
    builder.add_edge("summarize", "assistant")

    builder.add_node("assistant", run_node_fn)
    agent_tools = [t for t in tools if t.name != "get_facts_tool"]
    builder.add_node("tools", ToolNode(tools=agent_tools))
    
    builder.add_conditional_edges("assistant", tools_condition, {"tools": "tools", END: END})
    builder.add_edge("tools", "assistant")

    return builder.compile(checkpointer=checkpointer)
```
- В `LangGraphAssistant`:
    - Убедиться, что `GetFactsTool` создается и передается в `build_full_graph`.
    - Установить `initial_state_template` с `llm_context_size` и `user_id`.
    - **Важно:** Функция `run_node_fn` (узел `assistant`) должна обновлять и возвращать `current_token_count` после добавления ответа LLM.

### Итерация 6. End-to-end тесты
- Файл `tests/test_memory_pipeline_e2e.py`.
- Обновить/добавить тесты:
    - Проверка вызова `GetFactsTool` при первом запуске (`facts_loaded=False`).
    - Проверка вызова `GetFactsTool` при `fact_added_in_last_run=True`.
    - Проверка *не* вызова `GetFactsTool` при `fact_added_in_last_run=False` и `facts_loaded=True`.
    - Проверка корректной вставки/замены `SystemMessage` с фактами.
    - Проверка обновления `current_token_count` в узлах `load_facts`, `summarize_history`, `assistant`.
    - **Тест:** `pending_facts=[]` (после `check_facts`) -> граф проходит до `assistant` без ошибок.
    - **Тест:** Пограничный случай `token_count / llm_context_size == 0.6` -> переход к `summarize`.
    - **Тест:** Случай ошибки при вызове `GetFactsTool` -> граф продолжает работу без фактов.

