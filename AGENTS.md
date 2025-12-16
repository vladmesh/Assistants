# High-Level Overview

Актуальное состояние монорепы Smart Assistant.

## Структура
```
smart-assistant/
├── assistant_service/        # LangGraph-ассистент, очереди Redis
├── rest_service/             # FastAPI + Postgres (pgvector), бизнес-данные
├── google_calendar_service/  # OAuth2 + события календаря
├── cron_service/             # APScheduler, триггеры напоминаний → Redis
├── telegram_bot_service/     # Telegram-бот, мост к Redis/REST
├── rag_service/              # RAG API, OpenAI embeddings
├── admin_service/            # Streamlit-панель поверх REST (мониторинг)
├── monitoring/               # Grafana + Prometheus + Loki
├── shared_models/            # Общие схемы/enum
├── scripts/, docs/           # Утилиты и дизайн-доки
├── Makefile                  # lint/format/tests (ruff + docker)
├── docker-compose.yml        # Основной стенд (dev)
├── docker-compose.unit-test.yml / docker-compose.integration.yml
└── .pre-commit-config.yaml   # hooks: make format, make lint+test-unitUpgrade tornado to fix 1 Dependabot alert in admin_service/poetry.lock
Upgrade tornado to version 6.5 or later.
```

## Ключевые технологии
- Python 3.11, Poetry per-service.
- FastAPI (rest/rag/calendar), Streamlit (admin).
- LangChain 1.x + LangGraph 1.x в `assistant_service` (middleware архитектура).
- Postgres (pgvector), Redis.
- RAG: без внешней векторной БД (in-memory реализация).
- OpenAI (chat + embeddings), Tavily web-search (опционально).
- Линт/формат: Ruff (format + check). Тесты: Pytest. Логи: structlog.
- Мониторинг: Grafana + Prometheus + Loki (в `monitoring/`).
- CI/CD: GitHub Actions (lint, unit, integration, GHCR build/push, deploy).

## Сервисы (кратко)
- `assistant_service`: LangGraph оркестратор, читает `REDIS_QUEUE_TO_SECRETARY`, пишет в `REDIS_QUEUE_TO_TELEGRAM`, хранит сообщения/факты через REST+Postgres, использует инструменты (календарь, напоминания, sub-assistants, web-search, RAG).
- `rest_service`: FastAPI + SQLModel/pgvector. CRUD пользователей, ассистентов, инструментов, напоминаний, фактов; отдаёт конфигурации тулов.
- `telegram_bot_service`: приём/отправка сообщений Telegram, резолвит пользователей через REST, мостит события в Redis очереди.
- `cron_service`: тянет активные напоминания из REST, шлёт `reminder_triggered` в `REDIS_QUEUE_TO_SECRETARY`.
- `google_calendar_service`: OAuth2 токены и операции с календарём, взаимодействует с REST и Redis.
- `rag_service`: REST API для добавления/поиска эмбеддингов. Использует OpenAI embeddings, хранение пока in-memory.
- `admin_service`: Streamlit UI поверх REST (конфиг/мониторинг).
- `shared_models`: общие Pydantic-схемы/enum для всех сервисов.

## Локальный запуск
- Подготовить `.env`: `POSTGRES_*`, `ASYNC_DATABASE_URL`, `REDIS_HOST/PORT/DB`, `REDIS_QUEUE_TO_TELEGRAM`, `REDIS_QUEUE_TO_SECRETARY`, `OPENAI_API_KEY`, `TELEGRAM_TOKEN`, `REST_SERVICE_URL`, `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`.
- Запуск dev-стенда: `docker compose up --build -d`. Код монтируется как volume, healthcheck-и включены.
- Управление: `docker compose ps`, `docker compose logs -f <service>`, `docker compose restart <service>`.
- Мониторинг (опционально): `cd monitoring && docker compose -f docker-compose.monitoring.yml --env-file ../.env up -d`. Grafana: http://localhost:3000.

## Makefile workflow (dockerized Ruff/Pytest)
- `make format [SERVICE=...]` — ruff format + ruff check --fix.
- `make format-check [SERVICE=...]` — ruff format --check.
- `make lint [SERVICE=...]` — ruff check.
- `make build-test-base` — собирает базовый образ `assistants-test-base` (pytest + shared_models).
- `make test-unit [SERVICE=...]` — docker-compose.unit-test (без БД/Redis, env из tests/.env.test).
- `make test-integration [SERVICE=rest_service|assistant_service|telegram_bot_service|all]` — docker-compose.integration (pgvector + redis).
- `make test-all` — unit + integration подряд.
- Pre-commit: на commit `make format`, на push `make lint && make test-unit`.

## CI/CD (GitHub Actions)
- `ci.yml`: matrix формат-чек + lint для всех сервисов, затем unit (все), затем integration (rest/assistant/telegram).
- `docker-publish.yml`: build & push образов в GHCR для основных сервисов по ветке `main`.
- `deploy-prod.yml`: ручной dispatch или тег `v*`; SSH на прод и `docker compose pull && up -d` с `IMAGE_TAG`.

## Очереди и потоки
- Вход: Telegram → `REDIS_QUEUE_TO_SECRETARY` (`HumanMessage`), Cron → `REDIS_QUEUE_TO_SECRETARY` (`reminder_triggered`).
- Обработка: `assistant_service` → REST (состояние/факты) → инструменты (календарь, напоминания, RAG, web-search).
- Выход: ответы в `REDIS_QUEUE_TO_TELEGRAM` → `telegram_bot_service` → пользователь.

## Тестовые конфиги
- `docker-compose.unit-test.yml`: монтирует `${SERVICE}`, `shared_models`, использует env из `tests/.env.test`, ставит зависимости Poetry без venv, запускает `pytest tests/unit`.
- `docker-compose.integration.yml`: поднимает pgvector и redis, переменные `ASYNC_DATABASE_URL`, `REDIS_URL`, тестовые очереди; команда pytest для `tests/integration` либо fallback на все тесты.

## Мониторинг
- Инфраструктура: Grafana (дашборды), Prometheus (метрики), Loki (логи), Promtail (сбор логов).
- Метрики: HTTP запросы, ошибки, размеры очередей, выполнение джобов (cron_service).
- Логи: структурированные (structlog), с correlation_id, собираются из Docker контейнеров.
- Алерты: Telegram-уведомления при критических проблемах (сервис недоступен, высокий уровень ошибок).
- Админка: страницы мониторинга в `admin_service` (logs, metrics, queues, jobs).

## Прочее
- Миграции rest_service: `make migrate MESSAGE="..."` создаёт alembic revision внутри контейнера; цели upgrade/history пока заглушки в Makefile.
- Дополнительные планы/идеи — каталог `docs/` (memory/RAG/refactoring/testing/monitoring и др.).

## Architecture Decision Records

### ADR-001: LangGraph + LangChain как основной фреймворк
- LangChain 1.x + LangGraph 1.x с middleware архитектурой.
- Один тип ассистента (LLM), контекст хранится в Postgres через REST.
