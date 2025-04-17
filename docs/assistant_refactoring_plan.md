# План Рефакторинга Assistant Service: Наследие и Стандартизация

**Цель:** Модернизировать структуру классов ассистентов в `assistant_service`, удалив устаревшую реализацию OpenAI Assistants API, внедрив четкую систему наследования для поддержки LangGraph и будущих non-LangGraph реализаций, стандартизировав типы сообщений и обновив зависимости, сохраняя при этом совместимость с существующей конфигурацией и обеспечивая надежное тестирование на каждом этапе.

**Важные Замечания:**

1.  **Docker:** Файлы `Dockerfile`, `Dockerfile.test` и `docker-compose*.yml` **не трогаем**, если нет абсолютной необходимости. При крайней необходимости изменения должны строго соответствовать шаблону в корне проекта.
2.  **Тестирование:** После **каждого** инкремента выполняется полный цикл тестирования с использованием **тестового docker compose**.
3.  **Инкрементальность:** План разбит на минимально возможные шаги для снижения рисков.
4.  **Git:** Каждый успешно протестированный инкремент завершается коммитом и пушем. `git status` перед `git add`. Коммиты только на английском.

---

## Инкремент 1: Обновление Зависимостей

**Задача:** Обновить ключевые библиотеки, связанные с LangChain и LangGraph, до последних стабильных версий для обеспечения совместимости и доступа к новым функциям.

**Шаги:**

1.  **Исследование:** Проверить последние стабильные версии для:
    *   `langchain`
    *   `langgraph`
    *   `langchain-openai` (или соответствующий пакет для используемых LLM)
    *   `langchain-core`
    *   `psycopg` (или `psycopg[binary]`, `psycopg-binary` - проверить, что используется для `AsyncPostgresSaver`)
    *   Другие релевантные `langchain-*` пакеты.
2.  **Обновление `pyproject.toml`:**
    *   Открыть `pyproject.toml` в корне проекта.
    *   Обновить номера версий для перечисленных библиотек в секции `[tool.poetry.dependencies]`. Используйте `^` или `>=` синтаксис, как принято в проекте, но зафиксируйте мажорные версии для стабильности.
3.  **Обновление Зависимостей:**
    *   Выполнить в корне проекта:
        ```bash
        poetry lock --no-update
        poetry install
        ```
        *(`--no-update` предотвратит обновление *всех* зависимостей, обновляя только явно измененные и их под-зависимости. Если возникнут конфликты, возможно, придется убрать флаг или решать их вручную).*
4.  **Проверка `requirements.txt`:** Убедиться, что в `assistant_service/requirements.txt` нет жестко зафиксированных версий этих библиотек, которые могли бы конфликтовать с `pyproject.toml`. В идеале, специфичные для сервиса зависимости должны управляться через Poetry группы или быть минимальными.

**Тестирование (Инкремент 1):**

1.  **Запуск тестов через compose:**
    ```bash
    docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
    ```
    Убедиться, что все контейнеры успешно завершили работу (exit code 0). Особое внимание на логи контейнера `assistant_service-test`.
2.  **Запуск сервисов:** `docker compose up --build -d`. Следить за логами `assistant_service` на предмет ошибок импорта или инициализации, особенно связанных с обновленными библиотеками и `AsyncPostgresSaver`.
3.  **Базовая проверка:** Если сервисы стартовали, эмулировать отправку простого сообщения (через REST API `telegram_bot_service` или напрямую в Redis `REDIS_QUEUE_TO_SECRETARY`). Проверить логи `assistant_service` на предмет успешной обработки и отсутствия ошибок сериализации/чекпоинтера.
4.  **Git:** Если все тесты и проверки прошли:
    ```bash
    git status
    git add pyproject.toml poetry.lock assistant_service/requirements.txt # (если менялся)
    git commit -m "feat(deps): update langchain and langgraph libraries"
    git push
    ```

---

## Инкремент 2: Отказ от Кастомных Сообщений

**Задача:** Заменить самописные классы сообщений (HumanMessage, ToolMessage и т.д.) на стандартные из `langchain_core.messages` для улучшения сериализации и совместимости с LangGraph Checkpointer.

**Шаги:**

1.  **Поиск Использования:** Найти все места в `assistant_service`, где используются кастомные классы сообщений. Вероятно, это будет:
    *   Определение состояния графа (`State` в `BaseLLMChat` или будущем `LangGraphChatRunner`).
    *   Внутри узлов графа при обработке или добавлении сообщений.
    *   Возможно, при парсинге входных данных или форматировании выходных.
    *   Файлы, где были определены сами кастомные классы (их нужно будет удалить).
2.  **Замена Импортов:** Заменить импорты кастомных классов на импорты из `langchain_core.messages`:
    ```python
    # Было (примерно):
    # from assistant_service.src.models.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

    # Стало:
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage, BaseMessage, AnyMessage # AnyMessage может быть полезен для State
    ```
3.  **Замена Использования:** Заменить все использования кастомных классов на стандартные. Особое внимание уделить сигнатуре состояния графа:
    ```python
    # В определении State (TypedDict) графа
    # Было (примерно):
    # messages: Annotated[list[CustomBaseMessage], add_messages]
    # Стало:
    messages: Annotated[list[BaseMessage], add_messages] # Или list[AnyMessage] если используете AnyMessage
    ```
4.  **Удаление Кастомных Классов:** Удалить файлы, где были определены кастомные классы сообщений.

**Тестирование (Инкремент 2):**

1.  **Запуск тестов через compose:**
    ```bash
    docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
    ```
    Убедиться, что все тесты проходят, особенно те, что работают с графом, состоянием и сообщениями.
2.  **Запуск сервисов:** `docker compose up --build -d`.
3.  **Проверка Чекпоинтера:** Эмулировать отправку сообщения. Проверить:
    *   Логи `assistant_service` на отсутствие ошибок сериализации/десериализации при работе `AsyncPostgresSaver`.
    *   Содержимое таблицы чекпоинтов в БД (`langgraph_checkpoints` или аналогичной) - данные должны корректно записываться.
    *   Возможность продолжить диалог (если чекпоинтер загружает предыдущее состояние).
4.  **Git:** Если все тесты и проверки прошли:
    ```bash
    git status
    git add . # Добавить измененные/удаленные файлы
    git commit -m "refactor(assistant): replace custom messages with langchain_core messages"
    git push
    ```

---

## Инкремент 3: Удаление Реализации OpenAI Assistants API

**Задача:** Полностью удалить код, связанный с устаревшей реализацией на базе OpenAI Assistants API.

**Шаги:**

1.  **Идентификация:** Найти все файлы, классы, функции и конфигурации, относящиеся к `OpenAIAssistant`. Скорее всего, это будет отдельный файл (например, `openai_assistant.py`) и упоминания в `factory.py`.
2.  **Удаление Файлов:** Удалить основной файл реализации (например, `openai_assistant.py`).
3.  **Чистка Фабрики:** Открыть `assistant_service/src/assistants/factory.py`. Удалить:
    *   Импорт `OpenAIAssistant`.
    *   Логику в `get_assistant`, которая проверяет тип "openai" и создает экземпляр `OpenAIAssistant`.
4.  **Чистка Конфигураций (если применимо):** Проверить, нет ли в `rest_service` или других местах настроек, специфичных только для OpenAI ассистентов, которые больше не нужны. (Само удаление данных из БД не входит в этот шаг, но нужно помнить).

**Тестирование (Инкремент 3):**

1.  **Запуск тестов через compose:**
    ```bash
    docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
    ```
    Убедиться, что тесты проходят (тесты, специфичные для OpenAI, должны были быть удалены или адаптированы ранее).
2.  **Запуск сервисов:** `docker compose up --build -d`. Проверить логи `assistant_service` на отсутствие ошибок при старте и инициализации фабрики.
3.  **Проверка Фабрики:** Попробовать (если возможно) запросить через `rest_service` создание/получение ассистента, который *раньше* был типа "openai". Фабрика должна либо выдать ошибку (если тип жестко задан), либо корректно создать `LangGraphAssistant`, если логика выбора типа была адаптирована (например, по умолчанию используется "langgraph").
4.  **Git:** Если все тесты и проверки прошли:
    ```bash
    git status
    git add . # Добавить измененные/удаленные файлы
    git commit -m "refactor(assistant): remove obsolete OpenAI Assistants API implementation"
    git push
    ```

---

## Инкремент 4: Введение Абстрактного `BaseAssistant`

**Задача:** Создать абстрактный базовый класс для всех типов ассистентов.

**Шаги:**

1.  **Создание Файла:** Создать файл `assistant_service/src/assistants/base_assistant.py`.
2.  **Определение Класса:** Реализовать класс `BaseAssistant`, как было предложено ранее:
    ```python
    # assistant_service/src/assistants/base_assistant.py
    from abc import ABC, abstractmethod
    from typing import Any, List, Dict

    class BaseAssistant(ABC):
        """Defines the common interface for all assistant implementations."""
        def __init__(self, assistant_id: str, name: str, config: Dict, tools: List, llm_config: Dict, **kwargs):
            self.assistant_id = assistant_id
            self.name = name
            self.config = config # General assistant config
            self.tools = tools   # List of available tool configurations from DB
            self.llm_config = llm_config # LLM specific config (model name, api keys etc)
            # Store kwargs if they contain useful info like 'role' or 'is_secretary'
            self.additional_params = kwargs

        @abstractmethod
        async def process_message(self, message_input: Any, user_id: str, thread_id: str, invoke_config: Dict) -> Any:
            """Processes an incoming message and returns the assistant's response."""
            pass

        # Optional: Add helper method for tool initialization if common logic exists
        # def _initialize_tools(self, tool_registry): ...
    ```
3.  **Инициализация `__init__.py`:** Убедиться, что в `assistant_service/src/assistants/__init__.py` есть импорт `BaseAssistant` (или он пустой, что тоже нормально).

**Тестирование (Инкремент 4):**

1.  **Запуск тестов через compose:**
    ```bash
    docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
    ```
    Этот шаг не должен ничего сломать, так как класс пока не используется. Проверяем на синтаксические ошибки.
2.  **Git:** Если тесты прошли:
    ```bash
    git status
    git add assistant_service/src/assistants/base_assistant.py assistant_service/src/assistants/__init__.py
    git commit -m "feat(assistant): introduce BaseAssistant abstract class"
    git push
    ```

---

## Инкремент 5: Рефакторинг `LangGraphAssistant`

**Задача:** Переименовать и реструктурировать текущую реализацию ассистента на базе LangGraph, унаследовав её от `BaseAssistant`.

**Шаги:**

1.  **Переименование/Создание Файла:** Переименовать существующий файл (например, `llm_chat.py`) в `langgraph_assistant.py` или создать новый, если рефакторинг удобнее делать так.
2.  **Класс `LangGraphChatRunner`:** Выделить логику построения и компиляции графа (вероятно, из текущего `BaseLLMChat` или аналогичного класса) в отдельный класс `LangGraphChatRunner` внутри `langgraph_assistant.py`. Этот класс будет принимать `llm`, `tools`, `system_prompt` и отвечать за `_create_graph` и `compile`.
3.  **Класс `LangGraphAssistant`:**
    *   Создать класс `LangGraphAssistant`, унаследованный от `BaseAssistant`.
    *   Реализовать `__init__`:
        *   Вызвать `super().__init__(...)`.
        *   Принять `checkpointer: BaseCheckpointSaver` как аргумент.
        *   Сохранить `system_prompt`.
        *   Реализовать `_initialize_llm(self.llm_config)` для создания экземпляра LLM.
        *   Реализовать `_initialize_tools(self.tools)` для создания экземпляров инструментов LangChain/LangGraph (возможно, с использованием некоего реестра инструментов).
        *   Создать экземпляр `LangGraphChatRunner`.
        *   Скомпилировать граф: `self.compiled_graph = self.runner.compile(checkpointer=checkpointer)`.
    *   Реализовать `process_message`:
        *   Сформировать `config` для `astream` / `ainvoke`, включая `{"configurable": {"thread_id": thread_id, ...}}`.
        *   Вызвать `self.compiled_graph.astream(...)` или `ainvoke`.
        *   Обработать результат и вернуть его.
4.  **Импорты:** Обновить импорты в этом файле.

**Тестирование (Инкремент 5):**

1.  **Запуск тестов через compose:**
    ```bash
    docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
    ```
    Это **ключевой** шаг рефакторинга. Тесты должны проверять инициализацию ассистента, создание графа, обработку сообщений и работу чекпоинтера.
2.  **Запуск сервисов:** `docker compose up --build -d`. Проверить логи на ошибки инициализации `LangGraphAssistant`.
3.  **Полная Проверка:** Эмулировать отправку сообщения. Проверить:
    *   Корректность ответа ассистента.
    *   Запись в чекпоинтер.
    *   Вызов инструментов (если применимо).
4.  **Git:** Если все тесты и проверки прошли:
    ```bash
    git status
    git add . # Добавить измененные/переименованные файлы
    git commit -m "refactor(assistant): implement LangGraphAssistant inheriting from BaseAssistant"
    git push
    ```

---

## Инкремент 6: Обновление `AssistantFactory`

**Задача:** Адаптировать фабрику для работы с новой структурой наследования и передачи чекпоинтера.

**Шаги:**

1.  **Редактирование `factory.py`:**
    *   Импортировать `BaseAssistant`, `LangGraphAssistant`.
    *   Изменить конструктор `__init__`, чтобы он принимал `checkpointer: BaseCheckpointSaver` и сохранял его в `self.checkpointer`. (Экземпляр чекпоинтера нужно будет создать там, где создается фабрика - вероятно, в `main.py` или при инициализации сервиса).
    *   Изменить `get_assistant`:
        *   Аннотация типа возвращаемого значения должна быть `BaseAssistant`.
        *   При создании экземпляра `LangGraphAssistant` передавать `self.checkpointer`.
        *   Убедиться, что все необходимые параметры (`assistant_id`, `name`, `config`, `tools`, `llm_config`, `system_prompt`, `**kwargs` для доп. параметров типа `role`) корректно извлекаются из `assistant_data` (полученного из `rest_service`) и передаются в конструктор `LangGraphAssistant`.
        *   Добавить заглушку/комментарий для обработки других `assistant_type` в будущем.
        *   Логика кэширования остается прежней.
2.  **Инициализация Фабрики:** Найти место, где создается экземпляр `AssistantFactory` (например, в `assistant_service/src/main.py`). Создать там экземпляр `AsyncPostgresSaver` и передать его в конструктор фабрики.

**Тестирование (Инкремент 6):**

1.  **Запуск тестов через compose:**
    ```bash
    docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
    ```
    Тесты должны проверять, что фабрика корректно создает `LangGraphAssistant` со всеми настройками и чекпоинтером.
2.  **Запуск сервисов:** `docker compose up --build -d`. Убедиться, что сервис стартует, чекпоинтер и фабрика инициализируются без ошибок.
3.  **Проверка Разных Ассистентов:** Если в `rest_service` настроены разные "секретари" (с разными ID, промптами, инструментами), эмулировать отправку сообщений каждому из них. Проверить, что фабрика создает для каждого свой корректный экземпляр `LangGraphAssistant`.
4.  **Git:** Если все тесты и проверки прошли:
    ```bash
    git status
    git add assistant_service/src/assistants/factory.py assistant_service/src/main.py # (или где инициализируется фабрика)
    git commit -m "refactor(assistant): update AssistantFactory for new inheritance and checkpointer injection"
    git push
    ```

---

Этот план обеспечивает поэтапный и контролируемый переход к новой структуре, минимизируя риски и позволяя тщательно тестировать изменения на каждом шаге. 