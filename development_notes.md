# Заметки по разработке

## Текущие задачи

### 1. Модульная структура хранения настроек и зависимостей ассистентов

#### Описание проблемы
В текущей реализации конфигурация ассистентов, их инструментов и промптов жестко закодирована в исходном коде. Это создает следующие ограничения:
- Необходимость пересборки сервиса для изменения конфигурации
- Сложность оперативного изменения настроек
- Отсутствие гибкости в управлении ассистентами
- Сложность добавления новых ассистентов и инструментов

#### Цель
Создать гибкую систему хранения и управления конфигурацией ассистентов, позволяющую:
- Динамически изменять настройки без пересборки
- Управлять ассистентами через административный интерфейс
- Создавать и настраивать новых ассистентов
- Модифицировать промпты и инструменты

#### Текущее состояние

1. **Реализованные модели данных**:
   ```sql
   -- Таблица ассистентов
   CREATE TABLE assistants (
       id UUID PRIMARY KEY,
       name VARCHAR(255),
       is_secretary BOOLEAN DEFAULT FALSE,
       model VARCHAR(255),
       instructions TEXT,
       assistant_type VARCHAR(50),  -- llm или openai_api
       openai_assistant_id VARCHAR(255),
       is_active BOOLEAN DEFAULT TRUE,
       created_at TIMESTAMP,
       updated_at TIMESTAMP
   );

   -- Типы инструментов (enum)
   CREATE TYPE tool_type AS ENUM (
       'calendar',
       'reminder',
       'time',
       'weather',
       'sub_assistant'
   );

   -- Таблица инструментов
   CREATE TABLE tools (
       id UUID PRIMARY KEY,
       name VARCHAR(255),
       tool_type tool_type,
       description TEXT,
       input_schema TEXT,  -- JSON схема входных данных в виде строки
       is_active BOOLEAN DEFAULT TRUE,
       created_at TIMESTAMP,
       updated_at TIMESTAMP
   );

   -- Связь ассистент-инструмент (many-to-many)
   CREATE TABLE assistant_tool_link (
       id UUID PRIMARY KEY,
       assistant_id UUID REFERENCES assistants(id),
       tool_id UUID REFERENCES tools(id),
       sub_assistant_id UUID REFERENCES assistants(id),
       is_active BOOLEAN DEFAULT TRUE,
       created_at TIMESTAMP,
       updated_at TIMESTAMP
   );

   -- Таблица тредов
   CREATE TABLE user_assistant_threads (
       id UUID PRIMARY KEY,
       user_id VARCHAR(255),
       assistant_id UUID REFERENCES assistants(id),
       thread_id VARCHAR(255),
       last_used TIMESTAMP,
       created_at TIMESTAMP,
       updated_at TIMESTAMP,
       UNIQUE(user_id, assistant_id)
   );
   ```

2. **Реализованные API Endpoints**:
   ```python
   # Управление ассистентами
   GET /assistants/ - список ассистентов ✅
   GET /assistants/{assistant_id} - получение ассистента ✅
   POST /assistants/ - создание ассистента ✅
   PUT /assistants/{assistant_id} - обновление ассистента ✅
   DELETE /assistants/{assistant_id} - удаление ассистента ✅

   # Управление инструментами
   GET /tools/ - список инструментов ✅
   GET /tools/{tool_id} - получение инструмента ✅
   POST /tools/ - создание инструмента ✅
   PUT /tools/{tool_id} - обновление инструмента ✅
   DELETE /tools/{tool_id} - удаление инструмента ✅

   # Управление связями ассистент-инструмент
   GET /assistants/{assistant_id}/tools - получение списка инструментов ассистента ✅
   POST /assistants/{assistant_id}/tools/{tool_id} - добавление инструмента ✅
   DELETE /assistants/{assistant_id}/tools/{tool_id} - удаление инструмента ✅
   ```

#### Необходимые доработки

1. **Расширение моделей данных** ✅
   - ✅ Добавить поле `name` в модель `Tool`
   - ✅ Добавить поле `input_schema` в модель `Tool` для JSON схемы входных данных
   - ❌ Добавить миграцию для новых полей

2. **API Endpoints для инструментов** ✅:
   ```python
   # Управление инструментами
   GET /tools/ - список инструментов ✅
   GET /tools/{tool_id} - получение инструмента ✅
   POST /tools/ - создание инструмента ✅
   PUT /tools/{tool_id} - обновление инструмента ✅
   DELETE /tools/{tool_id} - удаление инструмента ✅

   # Управление связями ассистент-инструмент
   GET /assistants/{assistant_id}/tools - получение списка инструментов ассистента ✅
   POST /assistants/{assistant_id}/tools/{tool_id} - добавление инструмента ✅
   DELETE /assistants/{assistant_id}/tools/{tool_id} - удаление инструмента ✅
   ```

3. **Валидация и кэширование**:
   - ✅ Реализовать валидацию JSON схем при создании/обновлении инструментов
   - ❌ Добавить кэширование настроек в Redis
   - ❌ Реализовать механизм обновления конфигурации

#### План реализации

1. **Этап 1: Расширение моделей** ✅
   - ✅ Создать базовые модели данных
   - ✅ Реализовать связи между моделями
   - ✅ Добавить поддержку тредов
   - ✅ Добавить новые поля в модель Tool
   - ❌ Создать миграцию для новых полей

2. **Этап 2: API Endpoints** ✅
   - ✅ Реализовать CRUD для ассистентов
   - ✅ Добавить CRUD для инструментов
   - ✅ Добавить управление связями ассистент-инструмент
   - ✅ Реализовать валидацию схем
   - ✅ Протестировать все эндпоинты

3. **Этап 3: Кэширование и обновление** ❌
   - ❌ Добавить кэширование в Redis
   - ❌ Реализовать механизм обновления
   - ❌ Добавить тесты для новых функций

#### Следующие шаги
1. Создать миграцию для добавления полей `name` и `input_schema` в таблицу `tools`
2. Реализовать кэширование в Redis
3. Добавить тесты для всех эндпоинтов 