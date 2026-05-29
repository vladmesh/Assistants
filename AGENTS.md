# High-Level Overview

Current state of the Smart Assistant monorepo.

## Structure
```
smart-assistant/
├── assistant_service/        # LangGraph assistant, Redis queues
├── rest_service/             # FastAPI + Postgres (pgvector), business data
├── google_calendar_service/  # OAuth2 + calendar events
├── cron_service/             # APScheduler, reminder triggers → Redis
├── telegram_bot_service/     # Telegram bot, bridge to Redis/REST
├── rag_service/              # RAG API, OpenAI embeddings
├── admin_service/            # Streamlit panel on top of REST (monitoring)
├── monitoring/               # Grafana + Prometheus + Loki
├── shared_models/            # Shared schemas/enums
├── scripts/, docs/           # Utilities and design docs
├── Makefile                  # lint/format/tests (ruff + docker)
├── docker-compose.yml        # Main stack (dev)
├── docker-compose.unit-test.yml / docker-compose.integration.yml
└── .pre-commit-config.yaml   # hooks: make format, make lint+test-unit
```

## Key Technologies
- Python 3.11, Poetry per service.
- FastAPI (rest/rag/calendar), Streamlit (admin).
- LangChain 1.x + LangGraph 1.x in `assistant_service` (middleware architecture).
- Postgres (pgvector), Redis.
- RAG: no external vector DB (in-memory implementation).
- OpenAI (chat + embeddings), Tavily web search (optional).
- Lint/format: Ruff (format + check). Tests: Pytest. Logs: structlog.
- Monitoring: Grafana + Prometheus + Loki (in `monitoring/`).
- CI/CD: GitHub Actions (lint, unit, integration, GHCR build/push, deploy).

## Services (brief)
- `assistant_service`: LangGraph orchestrator, reads `REDIS_QUEUE_TO_SECRETARY`, writes to `REDIS_QUEUE_TO_TELEGRAM`, stores messages/facts via REST+Postgres, uses tools (calendar, reminders, sub-assistants, web search, RAG).
- `rest_service`: FastAPI + SQLModel/pgvector. CRUD for users, assistants, tools, reminders, facts; serves tool configurations.
- `telegram_bot_service`: receives/sends Telegram messages, resolves users via REST, bridges events into Redis queues.
- `cron_service`: pulls active reminders from REST, sends `reminder_triggered` to `REDIS_QUEUE_TO_SECRETARY`.
- `google_calendar_service`: OAuth2 tokens and calendar operations, interacts with REST and Redis.
- `rag_service`: REST API for adding/searching embeddings. Uses OpenAI embeddings; storage is in-memory for now.
- `admin_service`: Streamlit UI on top of REST (config/monitoring).
- `shared_models`: shared Pydantic schemas/enums for all services.

## Local Setup
- Prepare `.env`: `POSTGRES_*`, `ASYNC_DATABASE_URL`, `REDIS_HOST/PORT/DB`, `REDIS_QUEUE_TO_TELEGRAM`, `REDIS_QUEUE_TO_SECRETARY`, `OPENAI_API_KEY`, `TELEGRAM_TOKEN`, `REST_SERVICE_URL`, `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`.
- Start the dev stack: `docker compose up --build -d`. Code is mounted as a volume and healthchecks are enabled.
- Management: `docker compose ps`, `docker compose logs -f <service>`, `docker compose restart <service>`.
- Monitoring (optional): `cd monitoring && docker compose -f docker-compose.monitoring.yml --env-file ../.env up -d`. Grafana: http://localhost:3000.

## Makefile workflow (dockerized Ruff/Pytest)
- `make format [SERVICE=...]` — ruff format + ruff check --fix.
- `make format-check [SERVICE=...]` — ruff format --check.
- `make lint [SERVICE=...]` — ruff check.
- `make build-test-base` — builds the base `assistants-test-base` image (pytest + shared_models).
- `make test-unit [SERVICE=...]` — docker-compose.unit-test (no DB/Redis, env from tests/.env.test).
- `make test-integration [SERVICE=rest_service|assistant_service|telegram_bot_service|all]` — docker-compose.integration (pgvector + redis).
- `make test-all` — unit + integration in sequence.
- Pre-commit: on commit `make format`, on push `make lint && make test-unit`.

## CI/CD (GitHub Actions)
- `ci.yml`: matrix format-check + lint for all services, then unit (all), then integration (rest/assistant/telegram).
- `docker-publish.yml`: build & push images to GHCR for the main services on the `main` branch.
- `deploy-prod.yml`: manual dispatch or `v*` tag; SSH to production and `docker compose pull && up -d` with `IMAGE_TAG`.

## Queues and Flows
- Input: Telegram → `REDIS_QUEUE_TO_SECRETARY` (`HumanMessage`), Cron → `REDIS_QUEUE_TO_SECRETARY` (`reminder_triggered`).
- Processing: `assistant_service` → REST (state/facts) → tools (calendar, reminders, RAG, web search).
- Output: responses to `REDIS_QUEUE_TO_TELEGRAM` → `telegram_bot_service` → user.

## Test Configurations
- `docker-compose.unit-test.yml`: mounts `${SERVICE}` and `shared_models`, uses env from `tests/.env.test`, installs Poetry dependencies without a venv, runs `pytest tests/unit`.
- `docker-compose.integration.yml`: brings up pgvector and redis, sets `ASYNC_DATABASE_URL`, `REDIS_URL`, and test queues; runs pytest for `tests/integration` or falls back to all tests.

## Monitoring
- Infrastructure: Grafana (dashboards), Prometheus (metrics), Loki (logs), Promtail (log collection).
- Metrics: HTTP requests, errors, queue sizes, job execution (cron_service).
- Logs: structured (structlog), with correlation_id, collected from Docker containers.
- Alerts: Telegram notifications on critical issues (service down, high error rate).
- Admin panel: monitoring pages in `admin_service` (logs, metrics, queues, jobs).

## Dead Letter Queue (DLQ)

### Error-handling Mechanism

When message processing fails in `assistant_service`:
1. The retry counter is incremented (stored in the Redis key `msg_retry:{message_id}`).
2. If `retry_count < MAX_RETRIES` (3):
   - The message is NOT ACKed.
   - It stays in pending for reprocessing via xautoclaim (60s idle).
   - Exponential backoff: 1s, 2s, 4s.
3. If `retry_count >= MAX_RETRIES`:
   - The message is sent to the DLQ stream `{queue}:dlq`.
   - The original message is ACKed.
   - The retry count is cleared.

### DLQ REST API (`rest_service`)

- `GET /api/dlq/messages?queue=...&error_type=...&user_id=...` — list messages in the DLQ.
- `GET /api/dlq/stats?queue=...` — DLQ statistics (total, by_error_type, timestamps).
- `POST /api/dlq/messages/{id}/retry?queue=...` — resend a message to the main queue.
- `DELETE /api/dlq/messages/{id}?queue=...` — delete a message after triage.
- `DELETE /api/dlq/messages?queue=...&error_type=...` — clear the DLQ (optionally by error type).

### Prometheus Metrics

- `messages_dlq_total{error_type, queue}` — counter of messages in the DLQ.
- `message_processing_retries_total{queue}` — number of retry attempts.
- `dlq_size{queue}` — current DLQ size.
- `message_retry_count{queue, outcome}` — histogram of retry distribution until success/dlq.

### Operational Procedures

See `docs/dlq_operations_guide.md` for:
- Monitoring and alerts
- Error triage
- Message recovery
- DLQ cleanup

## Miscellaneous
- rest_service migrations: `make migrate MESSAGE="..."` creates an alembic revision inside the container; the upgrade/history targets are still stubs in the Makefile.
- Additional plans/ideas — the `docs/` directory (memory/RAG/refactoring/testing/monitoring, etc.).

## Architecture Decision Records

### ADR-001: LangGraph + LangChain as the core framework
- LangChain 1.x + LangGraph 1.x with a middleware architecture.
- A single assistant type (LLM); context is stored in Postgres via REST.
