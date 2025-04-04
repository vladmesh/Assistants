# План миграции на Poetry

## 1. Подготовка корневого проекта

### 1.1 Создание корневого pyproject.toml
1. Создать файл `pyproject.toml` в корне проекта
2. Настроить базовые параметры:
   ```toml
   [tool.poetry]
   name = "smart-assistant"
   version = "0.1.0"
   description = "Smart Assistant Project"
   authors = ["Your Name <your.email@example.com>"]
   packages = [
       { include = "shared_models" },
       { include = "assistant_service" },
       { include = "rest_service" },
       { include = "google_calendar_service" },
       { include = "cron_service" },
       { include = "telegram_bot_service" },
   ]
   ```
3. Добавить общие зависимости:
   - Python 3.11
   - Pydantic
   - FastAPI
   - SQLAlchemy
   - Redis
   - и другие общие пакеты

### 1.2 Настройка линтеров и форматтеров
1. Добавить dev-зависимости:
   ```toml
   [tool.poetry.group.dev.dependencies]
   black = "^23.10.1"
   isort = "^5.12.0"
   flake8 = "^6.1.0"
   mypy = "^1.6.1"
   ```
2. Настроить правила для каждого инструмента:
   ```toml
   [tool.black]
   line-length = 88
   target-version = ['py311']
   
   [tool.isort]
   profile = "black"
   multi_line_output = 3
   
   [tool.mypy]
   python_version = "3.11"
   disallow_untyped_defs = true
   ```

### 1.3 Настройка тестового окружения
1. Добавить test-зависимости:
   ```toml
   [tool.poetry.group.test.dependencies]
   pytest = "^7.4.3"
   pytest-asyncio = "^0.21.1"
   pytest-cov = "^4.1.0"
   pytest-mock = "^3.12.0"
   ```

## 2. Создание shared_models

### 2.1 Структура пакета
1. Создать директорию `shared_models`
2. Создать `pyproject.toml` для shared_models:
   ```toml
   [tool.poetry]
   name = "shared-models"
   version = "0.1.0"
   description = "Shared Pydantic models"
   packages = [{ include = "shared_models" }]
   
   [tool.poetry.dependencies]
   python = "^3.11"
   pydantic = "^2.4.2"
   ```

### 2.2 Миграция моделей
1. Перенести общие Pydantic модели из сервисов
2. Организовать модели по категориям:
   - calendar_models.py
   - user_models.py
   - notification_models.py
3. Добавить версионирование моделей

## 3. Миграция сервисов

### 3.1 Общий процесс для каждого сервиса
1. Создать `pyproject.toml` в директории сервиса
2. Настроить наследование от корневого проекта
3. Добавить специфичные зависимости
4. Настроить специфичные правила линтера
5. Обновить Dockerfile

### 3.2 Пример для assistant_service
```toml
[tool.poetry]
name = "assistant-service"
version = "0.1.0"
description = "Assistant Service"

[tool.poetry.dependencies]
python = "^3.11"
smart-assistant = { path = "..", develop = true }
shared-models = { path = "../shared_models", develop = true }
openai = "^1.3.0"
langchain = "^0.0.350"

[tool.poetry.group.dev.dependencies]
smart-assistant = { path = "..", develop = true }
shared-models = { path = "../shared_models", develop = true }

[tool.poetry.group.test.dependencies]
smart-assistant = { path = "..", develop = true }
shared-models = { path = "../shared_models", develop = true }
```

### 3.3 Обновление Dockerfile
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml poetry.lock ./
COPY shared_models ./shared_models
COPY assistant_service ./assistant_service

RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY assistant_service/src ./src

CMD ["python", "-m", "src.main"]
```

## 4. Обновление CI/CD

### 4.1 GitHub Actions
1. Обновить workflow для использования Poetry:
   ```yaml
   steps:
     - uses: actions/checkout@v3
     - uses: actions/setup-python@v4
     - name: Install Poetry
       run: |
         curl -sSL https://install.python-poetry.org | python3 -
     - name: Install dependencies
       run: poetry install
     - name: Run tests
       run: poetry run pytest
   ```

### 4.2 Pre-commit хуки
1. Добавить `.pre-commit-config.yaml`:
   ```yaml
   repos:
     - repo: https://github.com/psf/black
       rev: 23.10.1
       hooks:
         - id: black
     - repo: https://github.com/pycqa/isort
       rev: 5.12.0
       hooks:
         - id: isort
     - repo: https://github.com/pycqa/flake8
       rev: 6.1.0
       hooks:
         - id: flake8
   ```

## 5. Тестирование и валидация

### 5.1 Локальное тестирование
1. Проверить установку зависимостей
2. Проверить работу линтеров
3. Запустить тесты
4. Проверить сборку Docker-образов

### 5.2 Интеграционное тестирование
1. Проверить взаимодействие сервисов
2. Проверить работу shared_models
3. Проверить миграцию данных

## 6. Документация

### 6.1 Обновление README
1. Добавить инструкции по установке
2. Описать процесс разработки
3. Добавить примеры использования

### 6.2 Документация по миграции
1. Описать процесс миграции для новых сервисов
2. Добавить примеры конфигурации
3. Описать лучшие практики

## 7. Порядок миграции сервисов

1. assistant_service (основной сервис)
2. rest_service (зависит от shared_models)
3. google_calendar_service
4. cron_service
5. telegram_bot_service

## 8. Критерии успешной миграции

1. Все сервисы успешно собираются с Poetry
2. Тесты проходят успешно
3. Docker-образы собираются без ошибок
4. Размер production-образов уменьшен
5. Время сборки не увеличилось
6. Все зависимости актуальны и безопасны 