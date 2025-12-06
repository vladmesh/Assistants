# Docker Infrastructure Audit

**Дата аудита:** 2024-12-06  
**Статус:** Критический - требуется оптимизация

---

## Обзор

Проект содержит 7 микросервисов, каждый с отдельным Dockerfile для production и test окружений (14 образов суммарно). Текущая конфигурация приводит к избыточному потреблению дискового пространства и неэффективному использованию Docker кэша.

---

## Выявленные проблемы

### 1. Отсутствует `.dockerignore` (КРИТИЧНО)

**Влияние:** Каждая сборка копирует весь контекст проекта включая:
- `.git/` (~50-500MB)
- `__pycache__/`
- `.venv/`
- `.pytest_cache/`
- `.ruff_cache/`

**Решение:** Создать `.dockerignore` в корне проекта:

```gitignore
# Git
.git
.gitignore

# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.eggs/

# Virtual environments
.venv/
venv/
ENV/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Linting/Formatting
.ruff_cache/
.mypy_cache/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.*
!.env.example

# Docker
docker-compose.override.yml

# Misc
*.log
*.tmp
```

---

### 2. Неоптимальный порядок COPY в Dockerfile

**Текущий код (все сервисы):**
```dockerfile
COPY shared_models ./shared_models          # Меняется часто
COPY assistant_service/pyproject.toml ...   # Меняется редко
RUN poetry install                          # Кэш инвалидируется!
```

**Проблема:** `shared_models` меняется при каждом изменении кода, что инвалидирует кэш зависимостей.

**Решение:**
```dockerfile
# Сначала файлы зависимостей (меняются редко)
COPY assistant_service/pyproject.toml assistant_service/poetry.lock* ./assistant_service/

# Создать минимальную структуру shared_models для poetry
RUN mkdir -p ./shared_models && touch ./shared_models/__init__.py
COPY shared_models/pyproject.toml ./shared_models/ 2>/dev/null || true

# Установить зависимости (кэшируется!)
RUN poetry config virtualenvs.create false && \
    cd assistant_service && \
    poetry install --only main --no-interaction --no-ansi --no-root

# Потом код (меняется часто, но не инвалидирует кэш зависимостей)
COPY shared_models ./shared_models
COPY assistant_service/src/ /src/
```

---

### 3. Дублирование Dockerfile и Dockerfile.test

**Текущее состояние:** 7 сервисов × 2 файла = 14 Dockerfile с 90% дублирования кода.

**Решение:** Объединить через ARG:

```dockerfile
# Dockerfile (универсальный)
ARG INSTALL_TEST_DEPS="false"

FROM python:3.11-slim as builder
WORKDIR /

RUN pip install --no-cache-dir poetry==1.8.3

COPY ${SERVICE_NAME}/pyproject.toml ${SERVICE_NAME}/poetry.lock* ./${SERVICE_NAME}/
COPY shared_models ./shared_models

RUN poetry config virtualenvs.create false && \
    cd ${SERVICE_NAME} && \
    if [ "$INSTALL_TEST_DEPS" = "true" ]; then \
        poetry install --with test --no-interaction --no-ansi --no-root; \
    else \
        poetry install --only main --no-interaction --no-ansi --no-root; \
    fi

# ... остальное
```

**Использование:**
```bash
# Production
docker build --build-arg INSTALL_TEST_DEPS=false -t service:prod .

# Test
docker build --build-arg INSTALL_TEST_DEPS=true -t service:test .
```

---

### 4. Poetry устанавливается без версии

**Текущий код:**
```dockerfile
RUN pip install poetry  # Всегда latest
```

**Проблема:** Разные версии poetry могут генерировать разные lock-файлы.

**Решение:**
```dockerfile
RUN pip install --no-cache-dir poetry==1.8.3
```

---

### 5. Отсутствует использование BuildKit cache mounts

**Решение:** Добавить cache mounts для pip и poetry:

```dockerfile
# syntax=docker/dockerfile:1.7

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/pypoetry \
    poetry install --only main --no-interaction --no-ansi --no-root
```

---

### 6. Volumes в docker-compose.yml

**Текущий код:**
```yaml
volumes:
  - ./assistant_service/src:/src
```

**Статус:** Это нормально для dev-режима, но образы всё равно пересобираются с полным кодом.

**Рекомендация:** Для dev-режима использовать отдельный `docker-compose.dev.yml` без пересборки образов:

```yaml
# docker-compose.dev.yml
services:
  assistant_service:
    image: python:3.11-slim
    command: python -m uvicorn main:app --reload --host 0.0.0.0
    volumes:
      - ./assistant_service/src:/src
      - ./shared_models:/shared_models
    # ... без build секции
```

---

## Рекомендуемые изменения

### Шаг 1: Создать `.dockerignore` (5 минут)
Создать файл в корне проекта с содержимым из раздела 1.

### Шаг 2: Создать общий base-image (30 минут)

```dockerfile
# docker/base/Dockerfile
FROM python:3.11-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir poetry==1.8.3

WORKDIR /
```

Собрать и использовать:
```bash
docker build -t assistants-base:latest -f docker/base/Dockerfile .
```

### Шаг 3: Рефакторинг Dockerfile сервисов (2 часа)

Обновить каждый Dockerfile:
1. Использовать `assistants-base:latest` как базовый образ
2. Исправить порядок COPY
3. Объединить prod/test через ARG
4. Добавить BuildKit cache mounts

### Шаг 4: Настроить автоочистку (15 минут)

Добавить в CI/CD или crontab:
```bash
# Очистка после каждой сборки
docker builder prune --keep-storage=5GB --force

# Еженедельная полная очистка
0 3 * * 0 docker system prune -a --volumes --force --filter "until=168h"
```

---

## Ожидаемый результат

| Метрика | До | После |
|---------|-----|-------|
| Размер build cache | ~12GB | ~3GB |
| Время первой сборки | ~5 мин | ~5 мин |
| Время повторной сборки (изменение кода) | ~3 мин | ~30 сек |
| Количество Dockerfile | 14 | 7 |
| Размер образа (каждый сервис) | ~800MB | ~600MB |

---

## Приоритет исправлений

1. **ВЫСОКИЙ:** Создать `.dockerignore` - мгновенный эффект
2. **ВЫСОКИЙ:** Исправить порядок COPY - ускорение сборок
3. **СРЕДНИЙ:** Объединить Dockerfile - уменьшение поддержки
4. **СРЕДНИЙ:** BuildKit cache mounts - дополнительная оптимизация
5. **НИЗКИЙ:** Общий base-image - долгосрочная оптимизация
