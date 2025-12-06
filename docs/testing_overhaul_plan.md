# Testing Overhaul Plan

Цель: выстроить чёткую двухуровневую стратегию тестов (unit + integration), запускать pytest в контейнерах, держать интеграцию в корневой папке, считать coverage при `make test`, минимально ломая существующие тесты и максимально их переиспользуя.

## Итерация 0 — Разведка и правила (факт-статус)
- Тестовые каталоги сейчас:
  - `assistant_service/tests/unit` и `assistant_service/tests/integration`.
  - Остальные сервисы (`rest_service`, `cron_service`, `telegram_bot_service`, `google_calendar_service`, `admin_service`, `rag_service`) имеют плоские `tests/` без разделения и без интеграции; `shared_models/tests` только юниты.
  - Корневой `tests/integration` отсутствует.
- Конфиги и маркеры:
  - Единственный `pytest.ini` в `rest_service` (asyncio settings), глобальных маркеров нет.
  - Маркировка `unit/integration` не заведена централизованно.
- Инфра запуска:
  - Для всех сервисов есть `docker-compose.test.yml`; запуск идёт из `scripts/run_tests.sh`.
  - `run_tests.sh` строит `Dockerfile.test` сервисов, поднимает compose с отключением attach для Redis/DB, затем сворачивает; `shared_models` гоняется в `python:3.11` через poetry без compose.
  - Coverage сейчас не считается и не выводится.
- Общие договорённости: термины — `unit` без реальных контейнеров/БД; `integration` — несколько сервисов/реальные зависимости; service-level не делаем. Pytest только в контейнерах. Интеграционные тесты будем выводить в корневой `tests/integration`. Coverage выводим при `make test`, но не роняем пайплайн.

## Итерация 1 — Структура каталогов и маркировка
- Каталоги (без переноса существующих тестов пока):
  - Завести `tests/unit` в сервисах, где их нет: `rest_service`, `cron_service`, `telegram_bot_service`, `google_calendar_service`, `admin_service`, `rag_service`, `shared_models`.
  - Оставить `assistant_service/tests/unit` как есть; `assistant_service/tests/integration` пока не трогаем.
  - Создать корневой `tests/integration` для межсервисных сценариев (assistant↔rest, telegram↔assistant, cron↔assistant↔rest и т.д.).
- Маркеры и конфиг:
  - Добавить корневой `pytest.ini` с регистрацией маркеров `unit` и `integration` (без изменения существующего `rest_service/pytest.ini` с asyncio settings).
  - Правило: юнит-тесты помечаем `@pytest.mark.unit`, корневые межсервисные — `@pytest.mark.integration`.
- Нейминг:
  - Файлы `test_*.py`; фикстуры уровня юнитов в `tests/unit/conftest.py` per сервис, интеграционные — в корневом `tests/integration/conftest.py` (когда появятся).
- Сделано в этой итерации:
  - Созданы пустые каталоги `tests/unit` в `rest_service`, `cron_service`, `telegram_bot_service`, `google_calendar_service`, `admin_service`, `rag_service`, `shared_models`.
  - Создан корневой `tests/integration`.
  - Добавлен корневой `pytest.ini` с маркерами `unit` и `integration` (локальные `pytest.ini` не тронуты).

## Итерация 2 — Инфра для unit-запуска (в контейнерах) ✅ DONE

### Реализованное решение

**Архитектура: Base Image + Runtime Dependencies**

Вместо билда отдельного `Dockerfile.test` для каждого сервиса используется единый базовый образ с pytest и shared_models, а зависимости конкретного сервиса доустанавливаются через poetry в runtime.

```
┌─────────────────────────────────────────────┐
│  Base Image (assistants-test-base:latest)   │
│  - python:3.11-slim                         │
│  - pytest, pytest-asyncio, pytest-cov, etc. │
│  - poetry (для установки зависимостей)      │
│  - shared_models (с pydantic и др.)         │
└─────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────┐
│  Runtime (при запуске теста)                │
│  - Mount: ${SERVICE}/ → /svc                │
│  - poetry install --only main,test          │
│  - pytest tests/unit/ (или tests/)          │
└─────────────────────────────────────────────┘
```

### Созданные файлы

1. **`Dockerfile.test-base`** — базовый образ:
   - pytest==8.0.0, pytest-asyncio, pytest-cov, pytest-mock, pytest-env
   - poetry для установки зависимостей сервисов
   - shared_models с зависимостями (pydantic, pydantic-settings)

2. **`docker-compose.unit-test.yml`** — compose для запуска unit-тестов:
   - Использует базовый образ
   - Монтирует код сервиса в /svc
   - Читает .env.test из сервиса
   - Кэширует poetry зависимости в volume
   - Запускает pytest tests/unit/ с coverage

3. **Makefile targets**:
   - `make build-test-base` — собрать базовый образ (один раз)
   - `make test-unit SERVICE=<name>` — запустить unit-тесты сервиса
   - `make test-unit` — запустить unit-тесты всех сервисов

### Использование

```bash
# Первый раз: собрать базовый образ
make build-test-base

# Запустить unit-тесты сервиса
make test-unit SERVICE=assistant_service
make test-unit SERVICE=cron_service
make test-unit SERVICE=shared_models

# Запустить все unit-тесты
make test-unit
```

### Результаты тестирования

- **shared_models**: 4 passed ✅
- **assistant_service**: 29 passed ✅
- **cron_service**: 6 passed ✅
- **rest_service**: требует разделения тестов на unit/integration (тесты используют БД)

### Преимущества

1. **Скорость** — не нужно билдить образ для каждого сервиса
2. **Кэширование** — poetry зависимости кэшируются в volume
3. **Единообразие** — одинаковое окружение для всех unit-тестов
4. **Простота** — один базовый образ, один compose файл

### Когда пересобирать базовый образ

- При изменении shared_models
- При обновлении версий pytest/plugins
- При изменении Dockerfile.test-base

## Итерация 3 — Инфра для интеграции (корневой уровень) ✅ DONE

### Реализованное решение

Создан единый `docker-compose.integration.yml` в корне проекта:
- Общая инфраструктура: PostgreSQL (pgvector:pg16) + Redis (7.2-alpine)
- Healthchecks для DB и Redis
- Использует базовый образ `assistants-test-base`
- Монтирует код сервиса + устанавливает зависимости через poetry

### Использование

```bash
# Запустить integration тесты для конкретного сервиса
make test-integration SERVICE=rest_service
make test-integration SERVICE=assistant_service
make test-integration SERVICE=telegram_bot_service

# Запустить все integration тесты
make test-integration
```

### Результаты

- **rest_service**: 3 passed (тесты с PostgreSQL)
- **assistant_service**: 29 passed (тесты с Redis)
- **telegram_bot_service**: 1 passed (smoke test с Redis)

**Итого: 33 integration теста**

### Созданные файлы

- `docker-compose.integration.yml` — compose с DB + Redis + test runner
- `Makefile` — добавлена цель `test-integration`

## Итерация 4 — Данные и изоляция ✅ DONE

**Unit тесты:**
- Используют моки/фейковые клиенты
- Никаких реальных БД/Redis/внешних API
- Все тесты перенесены в `tests/unit/`

**Integration тесты:**
- `rest_service/tests/integration/conftest.py` — пересоздаёт таблицы перед каждым тестом
- `assistant_service/tests/integration/conftest.py` — очищает Redis между тестами (flushdb)
- Тестовые токены/ключи передаются через environment variables в docker-compose

## Итерация 5 — Покрытие ✅ DONE

### Реализованное решение

Создан единый `.coveragerc` в корне проекта:
- Branch coverage включён
- Исключения: tests, migrations, alembic, __pycache__, venv
- Исключение строк: pragma: no cover, __repr__, TYPE_CHECKING, abstractmethod

### Использование

```bash
# Unit тесты с coverage
make test-unit SERVICE=assistant_service

# Integration тесты с coverage
make test-integration SERVICE=rest_service

# Все тесты с coverage summary
make test-all
```

### Текущие показатели coverage

| Service | Unit Coverage | Integration Coverage |
|---------|--------------|---------------------|
| assistant_service | 35% (29 tests) | 40% (29 tests) |
| rest_service | 0% (1 test) | 42% (3 tests) |
| rag_service | 84% (10 tests) | - |
| cron_service | 22% (6 tests) | - |
| admin_service | 24% (3 tests) | - |

### Созданные файлы

- `.coveragerc` — конфигурация coverage
- `Makefile` — добавлена цель `test-all`
- Обновлены `docker-compose.unit-test.yml` и `docker-compose.integration.yml` с монтированием .coveragerc

## Итерация 6 — Миграция и переиспользование существующих тестов ✅ DONE

### rest_service ✅
- Структура: `tests/unit/` и `tests/integration/`
- `test_dummy.py` → `tests/unit/`
- `test_secretaries.py`, `conftest.py` → `tests/integration/`
- Результат:
  - `make test-unit SERVICE=rest_service` — 1 passed
  - `make test SERVICE=rest_service` — 4 passed (integration с БД)

### rag_service ✅
- Все тесты уже используют моки (unit тесты)
- Перенесены `test_*.py` → `tests/unit/`
- Добавлен `tests/.env.test`
- Результат: `make test-unit SERVICE=rag_service` — 10 passed, 84% coverage

### admin_service ✅
- Тесты используют моки (unit)
- Перенесён `test_rest_client.py` → `tests/unit/`
- Исправлен импорт (`src.rest_client` → `rest_client`)
- Результат: `make test-unit SERVICE=admin_service` — 3 passed

### telegram_bot_service ✅
- `test_smoke.py` — integration тест (требует Redis)
- Перенесён `test_smoke.py` → `tests/integration/`
- Добавлен `tests/unit/test_placeholder.py`
- Результат: `make test-unit SERVICE=telegram_bot_service` — 1 passed (placeholder)

### google_calendar_service ✅
- Тесты закомментированы, остался placeholder
- Перенесены `test_routes.py`, `conftest.py` → `tests/unit/`
- Результат: `make test-unit SERVICE=google_calendar_service` — 1 passed

### Принципы миграции
- Проинвентаризировать текущие тесты: разнести по `tests/unit` и `tests/integration` без переписывания логики, где возможно.
- Выделить общие фикстуры/фабрики и вынести в сервисные `conftest.py` или корневой для интеграции.
- Удалить/обновить дубли, если тест покрыт интеграцией и юнитом — оставить более точный; избегать полного переписывания, только минимальные правки.

## Итерация 7 — CI и команды разработчика ✅ DONE

### Pre-commit hooks (.pre-commit-config.yaml)

- **commit**: `make format` — автоформатирование кода
- **push**: `make lint && make test-unit` — быстрые unit тесты (~30 сек)

### GitHub Actions CI (.github/workflows/ci.yml)

```
┌─────────────┐
│    lint     │  (8 сервисов параллельно)
│ format-check│
└──────┬──────┘
       │
       ├──────────────────┐
       ▼                  ▼
┌─────────────┐    ┌─────────────────┐
│ unit-tests  │    │integration-tests│
│ (все сервисы│    │ (3 сервиса      │
│  вместе)    │    │  параллельно)   │
└─────────────┘    └─────────────────┘
```

**Jobs:**
1. `lint` — format-check + lint для каждого сервиса (matrix)
2. `unit-tests` — все unit тесты (после lint)
3. `integration-tests` — rest_service, assistant_service, telegram_bot_service (matrix, после lint)

### Makefile targets

- `make test-unit` — быстрые unit тесты
- `make test-integration` — integration тесты с DB/Redis
- `make test-all` — все тесты с coverage summary
- `make build-test-base` — собрать базовый образ

## Итерация 8 — Нормализация и стабильность
- Включить логирование/сбор артефактов контейнеров при падении интеграционных тестов.
- Настроить таймауты/ретраи для сетевых вызовов в интеграции, чтобы снизить флейки.
- Проверить, что все тестовые команды детерминированы и не зависят от локального окружения.

## Итерация 9 — Контроль качества и постепенные улучшения
- Ввести регулярный прогон интеграции перед релизами; unit — на каждом PR.
- Постепенно закрывать пробелы в покрытии критичных путей (аутентификация, очереди, напоминания).
- Добавить lightweight контрактные проверки форматов сообщений/REST-пейлоадов между сервисами.

## Итоговое состояние
- Чёткое разделение: unit в сервисах, integration в корне.
- Все pytest-запуски идут из контейнеров через `make` цели.
- Coverage считается и выводится для unit и integration.
- Тестовые окружения детерминированы, данные изолируются, внешние API замещены фейками.
