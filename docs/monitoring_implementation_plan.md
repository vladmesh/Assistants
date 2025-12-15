# План внедрения мониторинга и observability

> **Цель:** Полноценная observability платформа для просмотра логов, метрик, состояния очередей, cron-джобов и памяти пользователей.

## Оглавление
1. [Обзор архитектуры](#1-обзор-архитектуры)
2. [Фаза 1: Стандартизация логирования](#фаза-1-стандартизация-логирования)
3. [Фаза 2: Инфраструктура мониторинга](#фаза-2-инфраструктура-мониторинга)
4. [Фаза 3: Инструментирование cron_service](#фаза-3-инструментирование-cron_service)
5. [Фаза 4: Observability очередей Redis](#фаза-4-observability-очередей-redis)
6. [Фаза 5: Метрики приложений](#фаза-5-метрики-приложений)
7. [Фаза 6: Расширение админки](#фаза-6-расширение-админки)
8. [Фаза 7: Алертинг](#фаза-7-алертинг)
9. [Конфигурация и переменные окружения](#конфигурация-и-переменные-окружения)

---

## 1. Обзор архитектуры

### Целевая архитектура
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Docker Compose                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  assistant   │  │  telegram    │  │    rest      │  │    cron      │   │
│  │   service    │  │    bot       │  │   service    │  │   service    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │           │
│         │ structlog JSON  │                 │                 │           │
│         ▼                 ▼                 ▼                 ▼           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Docker Logs                                  │   │
│  └─────────────────────────────┬───────────────────────────────────────┘   │
│                                │                                           │
│                                ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          Promtail                                     │  │
│  │            (собирает логи из Docker, парсит JSON)                     │  │
│  └────────────────────────────┬─────────────────────────────────────────┘  │
│                               │                                            │
│              ┌────────────────┴────────────────┐                           │
│              ▼                                 ▼                           │
│  ┌──────────────────┐              ┌──────────────────┐                   │
│  │      Loki        │              │   Prometheus     │                   │
│  │  (хранение логов)│              │    (метрики)     │                   │
│  │  retention: 48h  │              │                  │                   │
│  └────────┬─────────┘              └────────┬─────────┘                   │
│           │                                 │                             │
│           └────────────┬────────────────────┘                             │
│                        ▼                                                  │
│           ┌──────────────────────┐                                        │
│           │       Grafana        │                                        │
│           │   (дашборды, алерты) │──────▶ Telegram Alerts                │
│           │      :3000           │                                        │
│           └──────────────────────┘                                        │
│                        ▲                                                  │
│                        │                                                  │
│           ┌──────────────────────┐                                        │
│           │    Admin Service     │                                        │
│           │  (Streamlit + embed) │                                        │
│           └──────────────────────┘                                        │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Стек технологий
| Компонент | Версия | Назначение |
|-----------|--------|------------|
| Grafana Loki | 2.9.x | Агрегация и хранение логов |
| Promtail | 2.9.x | Сбор логов из Docker |
| Prometheus | 2.47.x | Сбор и хранение метрик |
| Grafana | 10.2.x | Визуализация, дашборды, алерты |

### Решение по трейсингу
**Не включаем OpenTelemetry tracing на данном этапе.** Причины:
- Проект не имеет сложных цепочек синхронных вызовов между сервисами
- Основной поток: Telegram → Redis Queue → Assistant → Redis Queue → Telegram (асинхронный)
- Для отладки достаточно correlation_id (request_id) в логах
- Добавление tracing увеличит сложность без значительной пользы

**Альтернатива:** Добавляем `correlation_id` во все логи для связывания событий одного запроса.

---

## Фаза 1: Стандартизация логирования

### Цель
Унифицировать формат логов во всех сервисах для эффективного парсинга в Loki.

### 1.1. Создание общего модуля логирования

**Файл:** `shared_models/src/shared_models/logging.py`

```python
import logging
import sys
from enum import Enum
from typing import Any
import structlog
from contextvars import ContextVar

# Context variable для correlation_id
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class LogEventType(str, Enum):
    """Типы событий для фильтрации в Loki."""
    REQUEST_IN = "request_in"
    REQUEST_OUT = "request_out"
    RESPONSE = "response"
    JOB_START = "job_start"
    JOB_END = "job_end"
    JOB_ERROR = "job_error"
    QUEUE_PUSH = "queue_push"
    QUEUE_POP = "queue_pop"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    MEMORY_SAVE = "memory_save"
    MEMORY_RETRIEVE = "memory_retrieve"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class LogLevel(str, Enum):
    """Уровни логирования."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def add_correlation_id(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Processor для добавления correlation_id."""
    cid = correlation_id_ctx.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def add_service_context(service_name: str):
    """Factory для processor, добавляющего имя сервиса."""
    def processor(
        logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        event_dict["service"] = service_name
        return event_dict
    return processor


def configure_logging(
    service_name: str,
    log_level: str = "INFO",
    json_format: bool = True,
) -> None:
    """
    Конфигурирует structlog для сервиса.
    
    Args:
        service_name: Имя сервиса (assistant_service, rest_service, etc.)
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        json_format: True для JSON (production), False для console (development)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    
    # Общие processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        add_service_context(service_name),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            parameters={
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            }
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Выбор renderer
    if json_format:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(
            structlog.dev.ConsoleRenderer(colors=True, sort_keys=True)
        )
    
    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Получить логгер с указанным именем."""
    return structlog.get_logger(name)


def set_correlation_id(cid: str) -> None:
    """Установить correlation_id для текущего контекста."""
    correlation_id_ctx.set(cid)


def get_correlation_id() -> str | None:
    """Получить текущий correlation_id."""
    return correlation_id_ctx.get()
```

### 1.2. Стандартный формат лога

Каждое сообщение должно содержать:

```json
{
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "level": "info",
  "service": "assistant_service",
  "event": "Processing user message",
  "event_type": "request_in",
  "correlation_id": "abc123-def456",
  "user_id": 42,
  "filename": "orchestrator.py",
  "lineno": 125,
  "func_name": "process_message",
  "extra_field": "any additional data"
}
```

### 1.3. Миграция сервисов

**Порядок миграции:**

1. **shared_models** — добавить модуль logging
2. **rest_service** — обновить, добавить middleware для correlation_id
3. **assistant_service** — обновить, генерировать correlation_id для входящих сообщений
4. **telegram_bot_service** — обновить
5. **cron_service** — перевести на structlog
6. **google_calendar_service** — обновить
7. **rag_service** — обновить
8. **admin_service** — обновить

**Для каждого сервиса:**

```python
# main.py или __init__.py
from shared_models.logging import configure_logging, get_logger

configure_logging(
    service_name="rest_service",
    log_level=settings.LOG_LEVEL,
    json_format=settings.ENVIRONMENT != "development"
)

logger = get_logger(__name__)
```

### 1.4. Обновление shared_models/pyproject.toml

Добавить structlog в зависимости:

```toml
[tool.poetry.dependencies]
python = "^3.11"
pydantic = "^2.0"
structlog = "^24.1.0"
```

### 1.5. Удаление дублирующегося кода

После миграции удалить:
- `assistant_service/src/config/logger.py`
- `google_calendar_service/src/config/logger.py`

---

## Фаза 2: Инфраструктура мониторинга

### Цель
Развернуть Loki, Promtail, Prometheus и Grafana в Docker Compose.

### 2.1. Структура файлов

```
monitoring/
├── docker-compose.monitoring.yml
├── promtail/
│   └── config.yml
├── prometheus/
│   └── prometheus.yml
├── loki/
│   └── loki-config.yml
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/
│   │   │   └── datasources.yml
│   │   ├── dashboards/
│   │   │   └── dashboards.yml
│   │   └── alerting/
│   │       └── alerting.yml
│   └── dashboards/
│       ├── overview.json
│       ├── logs.json
│       ├── cron-jobs.json
│       └── queues.json
└── alertmanager/
    └── config.yml  (optional, если нужен отдельный alertmanager)
```

### 2.2. docker-compose.monitoring.yml

```yaml
version: "3.8"

services:
  loki:
    image: grafana/loki:2.9.4
    container_name: loki
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki/loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:3100/ready || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  promtail:
    image: grafana/promtail:2.9.4
    container_name: promtail
    volumes:
      - ./monitoring/promtail/config.yml:/etc/promtail/config.yml:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/config.yml
    depends_on:
      loki:
        condition: service_healthy
    networks:
      - app_network

  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=48h'
      - '--web.enable-lifecycle'
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3

  grafana:
    image: grafana/grafana:10.2.3
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_ADMIN_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PW}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=${GRAFANA_ROOT_URL:-http://localhost:3000}
      - GF_ALERTING_ENABLED=true
      - GF_UNIFIED_ALERTING_ENABLED=true
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
    depends_on:
      loki:
        condition: service_healthy
      prometheus:
        condition: service_healthy
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:3000/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  loki_data:
  prometheus_data:
  grafana_data:

networks:
  app_network:
    external: true
    name: assistants_app_network
```

### 2.3. Конфигурация Loki

**Файл:** `monitoring/loki/loki-config.yml`

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

ruler:
  alertmanager_url: http://localhost:9093

limits_config:
  retention_period: 48h
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 4
  ingestion_burst_size_mb: 6

compactor:
  working_directory: /loki/compactor
  shared_store: filesystem
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150

analytics:
  reporting_enabled: false
```

### 2.4. Конфигурация Promtail

**Файл:** `monitoring/promtail/config.yml`

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
        filters:
          - name: label
            values: ["com.docker.compose.project=assistants"]
    relabel_configs:
      # Извлекаем имя контейнера
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.+)'
        target_label: container
      # Извлекаем имя сервиса из docker-compose
      - source_labels: ['__meta_docker_container_label_com_docker_compose_service']
        target_label: service
      # Извлекаем project name
      - source_labels: ['__meta_docker_container_label_com_docker_compose_project']
        target_label: project
    pipeline_stages:
      # Парсим JSON логи
      - json:
          expressions:
            level: level
            event_type: event_type
            user_id: user_id
            correlation_id: correlation_id
            service: service
            timestamp: timestamp
      # Добавляем labels для фильтрации
      - labels:
          level:
          event_type:
          service:
      # Устанавливаем timestamp из лога
      - timestamp:
          source: timestamp
          format: RFC3339Nano
          fallback_formats:
            - "2006-01-02T15:04:05.999999999Z07:00"
            - "2006-01-02 15:04:05.999999"
      # Добавляем structured metadata
      - structured_metadata:
          user_id:
          correlation_id:
```

### 2.5. Конфигурация Prometheus

**Файл:** `monitoring/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files: []

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # REST Service metrics
  - job_name: 'rest_service'
    static_configs:
      - targets: ['rest_service:8000']
    metrics_path: '/metrics'

  # Assistant Service metrics  
  - job_name: 'assistant_service'
    static_configs:
      - targets: ['assistant_service:8080']
    metrics_path: '/metrics'

  # Cron Service metrics
  - job_name: 'cron_service'
    static_configs:
      - targets: ['cron_service:8080']
    metrics_path: '/metrics'

  # RAG Service metrics
  - job_name: 'rag_service'
    static_configs:
      - targets: ['rag_service:8002']
    metrics_path: '/metrics'

  # Redis metrics (via redis_exporter)
  - job_name: 'redis'
    static_configs:
      - targets: ['redis_exporter:9121']

  # PostgreSQL metrics (via postgres_exporter)
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres_exporter:9187']
```

### 2.6. Provisioning Grafana Datasources

**Файл:** `monitoring/grafana/provisioning/datasources/datasources.yml`

```yaml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: true
    jsonData:
      maxLines: 1000
      derivedFields:
        - datasourceUid: prometheus
          matcherRegex: '"correlation_id":"([^"]+)"'
          name: correlation_id
          url: '$${__value.raw}'

  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: false
    jsonData:
      httpMethod: POST
      manageAlerts: true
      prometheusType: Prometheus
```

### 2.7. Provisioning Dashboards

**Файл:** `monitoring/grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1

providers:
  - name: 'Smart Assistant Dashboards'
    orgId: 1
    folder: 'Smart Assistant'
    folderUid: 'smart-assistant'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

### 2.8. Добавление exporters в основной docker-compose.yml

Добавить в `docker-compose.yml`:

```yaml
  redis_exporter:
    image: oliver006/redis_exporter:v1.55.0
    container_name: redis-exporter
    environment:
      - REDIS_ADDR=redis:6379
    ports:
      - "9121:9121"
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - app_network

  postgres_exporter:
    image: prometheuscommunity/postgres-exporter:v0.15.0
    container_name: postgres-exporter
    environment:
      - DATA_SOURCE_NAME=postgresql://${POSTGRES_USER}:***@db:5432/${POSTGRES_DB}?sslmode=disable
    ports:
      - "9187:9187"
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app_network
```

---

## Фаза 3: Инструментирование cron_service

### Цель
Добавить хранение истории выполнения джобов и экспорт метрик.

### 3.1. Модель для хранения истории джобов

**Файл:** `rest_service/src/models/job_execution.py`

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobExecution(SQLModel, table=True):
    """История выполнения cron-джобов."""
    
    __tablename__ = "job_executions"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: str = Field(index=True)  # ID джоба в APScheduler (e.g., "reminder_123")
    job_name: str  # Человекочитаемое имя
    job_type: str  # "reminder", "memory_extraction", "update_reminders"
    
    status: JobStatus = Field(default=JobStatus.SCHEDULED)
    
    scheduled_at: datetime  # Когда должен был запуститься
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None  # Длительность в миллисекундах
    
    # Контекст выполнения
    user_id: Optional[int] = Field(default=None, index=True)  # Для user-specific джобов
    reminder_id: Optional[int] = None  # Для напоминаний
    
    # Результат
    result: Optional[str] = None  # JSON с результатом
    error: Optional[str] = None  # Текст ошибки если failed
    error_traceback: Optional[str] = None  # Полный traceback
    
    # Метаданные
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    class Config:
        use_enum_values = True
```

### 3.2. CRUD для job_executions

**Файл:** `rest_service/src/crud/job_execution.py`

```python
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.job_execution import JobExecution, JobStatus


async def create_job_execution(
    session: AsyncSession,
    job_id: str,
    job_name: str,
    job_type: str,
    scheduled_at: datetime,
    user_id: Optional[int] = None,
    reminder_id: Optional[int] = None,
) -> JobExecution:
    """Создать запись о запланированном джобе."""
    job = JobExecution(
        job_id=job_id,
        job_name=job_name,
        job_type=job_type,
        scheduled_at=scheduled_at,
        user_id=user_id,
        reminder_id=reminder_id,
        status=JobStatus.SCHEDULED,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def start_job_execution(
    session: AsyncSession,
    execution_id: UUID,
) -> Optional[JobExecution]:
    """Отметить начало выполнения джоба."""
    job = await session.get(JobExecution, execution_id)
    if job:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)
        session.add(job)
        await session.commit()
        await session.refresh(job)
    return job


async def complete_job_execution(
    session: AsyncSession,
    execution_id: UUID,
    result: Optional[str] = None,
) -> Optional[JobExecution]:
    """Отметить успешное завершение джоба."""
    job = await session.get(JobExecution, execution_id)
    if job:
        job.status = JobStatus.COMPLETED
        job.finished_at = datetime.now(UTC)
        if job.started_at:
            job.duration_ms = int(
                (job.finished_at - job.started_at).total_seconds() * 1000
            )
        job.result = result
        session.add(job)
        await session.commit()
        await session.refresh(job)
    return job


async def fail_job_execution(
    session: AsyncSession,
    execution_id: UUID,
    error: str,
    error_traceback: Optional[str] = None,
) -> Optional[JobExecution]:
    """Отметить неудачное завершение джоба."""
    job = await session.get(JobExecution, execution_id)
    if job:
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(UTC)
        if job.started_at:
            job.duration_ms = int(
                (job.finished_at - job.started_at).total_seconds() * 1000
            )
        job.error = error
        job.error_traceback = error_traceback
        session.add(job)
        await session.commit()
        await session.refresh(job)
    return job


async def get_job_executions(
    session: AsyncSession,
    job_type: Optional[str] = None,
    status: Optional[JobStatus] = None,
    user_id: Optional[int] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[JobExecution]:
    """Получить историю выполнения джобов с фильтрами."""
    statement = select(JobExecution)
    
    if job_type:
        statement = statement.where(JobExecution.job_type == job_type)
    if status:
        statement = statement.where(JobExecution.status == status)
    if user_id:
        statement = statement.where(JobExecution.user_id == user_id)
    if since:
        statement = statement.where(JobExecution.created_at >= since)
    
    statement = (
        statement
        .order_by(JobExecution.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    result = await session.exec(statement)
    return result.all()


async def get_job_stats(
    session: AsyncSession,
    hours: int = 24,
) -> dict:
    """Получить статистику по джобам за последние N часов."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    
    statement = select(JobExecution).where(JobExecution.created_at >= since)
    result = await session.exec(statement)
    jobs = result.all()
    
    stats = {
        "total": len(jobs),
        "completed": sum(1 for j in jobs if j.status == JobStatus.COMPLETED),
        "failed": sum(1 for j in jobs if j.status == JobStatus.FAILED),
        "running": sum(1 for j in jobs if j.status == JobStatus.RUNNING),
        "scheduled": sum(1 for j in jobs if j.status == JobStatus.SCHEDULED),
        "avg_duration_ms": 0,
        "by_type": {},
    }
    
    durations = [j.duration_ms for j in jobs if j.duration_ms]
    if durations:
        stats["avg_duration_ms"] = sum(durations) // len(durations)
    
    for job in jobs:
        if job.job_type not in stats["by_type"]:
            stats["by_type"][job.job_type] = {"total": 0, "failed": 0}
        stats["by_type"][job.job_type]["total"] += 1
        if job.status == JobStatus.FAILED:
            stats["by_type"][job.job_type]["failed"] += 1
    
    return stats
```

### 3.3. API endpoints для job_executions

**Файл:** `rest_service/src/routers/job_executions.py`

```python
from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from crud.job_execution import (
    get_job_executions,
    get_job_stats,
)
from database import get_session
from models.job_execution import JobExecution, JobStatus

router = APIRouter(prefix="/job-executions", tags=["job-executions"])


@router.get("/", response_model=list[JobExecution])
async def list_job_executions(
    session: Annotated[AsyncSession, Depends(get_session)],
    job_type: Optional[str] = Query(None),
    status: Optional[JobStatus] = Query(None),
    user_id: Optional[int] = Query(None),
    hours: int = Query(24, ge=1, le=168),  # Max 7 days
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Получить список выполнений джобов с фильтрами."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    return await get_job_executions(
        session=session,
        job_type=job_type,
        status=status,
        user_id=user_id,
        since=since,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
async def get_jobs_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    hours: int = Query(24, ge=1, le=168),
):
    """Получить статистику по джобам."""
    return await get_job_stats(session, hours=hours)


@router.get("/{execution_id}", response_model=JobExecution)
async def get_job_execution(
    execution_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Получить детали выполнения джоба."""
    job = await session.get(JobExecution, execution_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job execution not found")
    return job
```

### 3.4. Обновление cron_service для записи истории

**Добавить в `cron_service/src/scheduler.py`:**

```python
import traceback
from datetime import datetime, UTC
from shared_models.logging import get_logger, LogEventType

logger = get_logger(__name__)


class JobExecutionTracker:
    """Трекер для записи выполнения джобов в REST API."""
    
    def __init__(self, rest_client):
        self.rest_client = rest_client
    
    async def on_job_scheduled(
        self,
        job_id: str,
        job_name: str,
        job_type: str,
        scheduled_at: datetime,
        user_id: int | None = None,
        reminder_id: int | None = None,
    ) -> str | None:
        """Записать запланированный джоб, вернуть execution_id."""
        try:
            response = await self.rest_client.post(
                "/job-executions/",
                json={
                    "job_id": job_id,
                    "job_name": job_name,
                    "job_type": job_type,
                    "scheduled_at": scheduled_at.isoformat(),
                    "user_id": user_id,
                    "reminder_id": reminder_id,
                }
            )
            return response.get("id")
        except Exception as e:
            logger.error("Failed to record job scheduled", error=str(e))
            return None
    
    async def on_job_start(self, execution_id: str) -> None:
        """Отметить начало выполнения."""
        try:
            await self.rest_client.patch(
                f"/job-executions/{execution_id}/start"
            )
            logger.info(
                "Job started",
                event_type=LogEventType.JOB_START,
                execution_id=execution_id,
            )
        except Exception as e:
            logger.error("Failed to record job start", error=str(e))
    
    async def on_job_complete(
        self,
        execution_id: str,
        result: str | None = None,
    ) -> None:
        """Отметить успешное завершение."""
        try:
            await self.rest_client.patch(
                f"/job-executions/{execution_id}/complete",
                json={"result": result}
            )
            logger.info(
                "Job completed",
                event_type=LogEventType.JOB_END,
                execution_id=execution_id,
            )
        except Exception as e:
            logger.error("Failed to record job completion", error=str(e))
    
    async def on_job_fail(
        self,
        execution_id: str,
        error: Exception,
    ) -> None:
        """Отметить неудачное завершение."""
        try:
            await self.rest_client.patch(
                f"/job-executions/{execution_id}/fail",
                json={
                    "error": str(error),
                    "error_traceback": traceback.format_exc(),
                }
            )
            logger.error(
                "Job failed",
                event_type=LogEventType.JOB_ERROR,
                execution_id=execution_id,
                error=str(error),
            )
        except Exception as e:
            logger.error("Failed to record job failure", error=str(e))
```

### 3.5. Prometheus метрики для cron_service

**Файл:** `cron_service/src/metrics.py`

```python
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Counters
jobs_total = Counter(
    'cron_jobs_total',
    'Total number of job executions',
    ['job_type', 'status']
)

# Gauges
scheduled_jobs = Gauge(
    'cron_scheduled_jobs',
    'Number of currently scheduled jobs',
    ['job_type']
)

# Histograms
job_duration_seconds = Histogram(
    'cron_job_duration_seconds',
    'Job execution duration in seconds',
    ['job_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)


def get_metrics():
    """Return metrics in Prometheus format."""
    return generate_latest()


def get_content_type():
    """Return Prometheus content type."""
    return CONTENT_TYPE_LATEST
```

### 3.6. HTTP сервер для метрик в cron_service

**Добавить в `cron_service/src/main.py`:**

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from metrics import get_metrics, get_content_type


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', get_content_type())
            self.end_headers()
            self.wfile.write(get_metrics())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress default logging


def start_metrics_server(port: int = 8080):
    """Start HTTP server for Prometheus metrics."""
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Metrics server started on port {port}")
    return server
```

---

## Фаза 4: Observability очередей Redis

### Цель
Добавить возможность просмотра состояния очередей и истории сообщений.

### 4.1. Модель для истории сообщений очереди

**Файл:** `rest_service/src/models/queue_message_log.py`

```python
from datetime import datetime, UTC
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text


class QueueDirection(str, Enum):
    INBOUND = "inbound"    # К assistant_service
    OUTBOUND = "outbound"  # От assistant_service


class QueueMessageLog(SQLModel, table=True):
    """Лог сообщений в очередях Redis."""
    
    __tablename__ = "queue_message_logs"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    queue_name: str = Field(index=True)  # "to_secretary" или "to_telegram"
    direction: QueueDirection
    
    # Идентификаторы
    correlation_id: Optional[str] = Field(default=None, index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    
    # Содержимое
    message_type: str  # "human", "tool", "trigger", "response"
    payload: str = Field(sa_column=Column(Text))  # JSON строка
    
    # Метаданные
    source: Optional[str] = None  # "telegram", "cron", "calendar", etc.
    processed: bool = Field(default=False)
    processed_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### 4.2. API для статистики очередей

**Файл:** `rest_service/src/routers/queue_stats.py`

```python
from datetime import datetime, timedelta, UTC
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models.queue_message_log import QueueMessageLog, QueueDirection

router = APIRouter(prefix="/queue-stats", tags=["queue-stats"])


class QueueStats(BaseModel):
    queue_name: str
    total_messages: int
    messages_last_hour: int
    messages_last_24h: int
    by_type: dict[str, int]
    by_source: dict[str, int]


@router.get("/", response_model=list[QueueStats])
async def get_queue_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """Получить статистику по всем очередям."""
    stats = []
    
    for queue_name in ["to_secretary", "to_telegram"]:
        # Total
        total_stmt = select(func.count()).where(
            QueueMessageLog.queue_name == queue_name
        )
        total = (await session.exec(total_stmt)).one()
        
        # Last hour
        hour_ago = datetime.now(UTC) - timedelta(hours=1)
        hour_stmt = select(func.count()).where(
            QueueMessageLog.queue_name == queue_name,
            QueueMessageLog.created_at >= hour_ago
        )
        last_hour = (await session.exec(hour_stmt)).one()
        
        # Last 24h
        day_ago = datetime.now(UTC) - timedelta(hours=24)
        day_stmt = select(func.count()).where(
            QueueMessageLog.queue_name == queue_name,
            QueueMessageLog.created_at >= day_ago
        )
        last_24h = (await session.exec(day_stmt)).one()
        
        # By type (last 24h)
        type_stmt = select(
            QueueMessageLog.message_type,
            func.count()
        ).where(
            QueueMessageLog.queue_name == queue_name,
            QueueMessageLog.created_at >= day_ago
        ).group_by(QueueMessageLog.message_type)
        type_results = (await session.exec(type_stmt)).all()
        by_type = {t: c for t, c in type_results}
        
        # By source (last 24h)
        source_stmt = select(
            QueueMessageLog.source,
            func.count()
        ).where(
            QueueMessageLog.queue_name == queue_name,
            QueueMessageLog.created_at >= day_ago
        ).group_by(QueueMessageLog.source)
        source_results = (await session.exec(source_stmt)).all()
        by_source = {s or "unknown": c for s, c in source_results}
        
        stats.append(QueueStats(
            queue_name=queue_name,
            total_messages=total,
            messages_last_hour=last_hour,
            messages_last_24h=last_24h,
            by_type=by_type,
            by_source=by_source,
        ))
    
    return stats


@router.get("/messages", response_model=list[QueueMessageLog])
async def get_queue_messages(
    session: Annotated[AsyncSession, Depends(get_session)],
    queue_name: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    correlation_id: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Получить историю сообщений очереди."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    
    statement = select(QueueMessageLog).where(
        QueueMessageLog.created_at >= since
    )
    
    if queue_name:
        statement = statement.where(QueueMessageLog.queue_name == queue_name)
    if user_id:
        statement = statement.where(QueueMessageLog.user_id == user_id)
    if correlation_id:
        statement = statement.where(QueueMessageLog.correlation_id == correlation_id)
    
    statement = (
        statement
        .order_by(QueueMessageLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    
    result = await session.exec(statement)
    return result.all()
```

### 4.3. Middleware для логирования сообщений очереди

Добавить в `assistant_service` и `telegram_bot_service` запись сообщений в REST API при push/pop из очереди.

**Пример для assistant_service:**

```python
async def log_queue_message(
    rest_client,
    queue_name: str,
    direction: str,
    message_type: str,
    payload: dict,
    user_id: int | None = None,
    correlation_id: str | None = None,
    source: str | None = None,
):
    """Записать сообщение очереди в лог."""
    try:
        await rest_client.post(
            "/queue-stats/log",
            json={
                "queue_name": queue_name,
                "direction": direction,
                "message_type": message_type,
                "payload": json.dumps(payload),
                "user_id": user_id,
                "correlation_id": correlation_id,
                "source": source,
            }
        )
    except Exception as e:
        logger.warning("Failed to log queue message", error=str(e))
```

### 4.4. Real-time метрики очередей Redis

**Добавить endpoint для текущего состояния очередей:**

```python
@router.get("/current")
async def get_current_queue_state(
    redis_client: Annotated[Redis, Depends(get_redis)],
):
    """Получить текущее состояние очередей."""
    to_secretary = await redis_client.llen("to_secretary_queue")
    to_telegram = await redis_client.llen("to_telegram_queue")
    
    return {
        "to_secretary": {
            "length": to_secretary,
            "oldest_message_age_seconds": None,  # TODO: если храним timestamp
        },
        "to_telegram": {
            "length": to_telegram,
            "oldest_message_age_seconds": None,
        }
    }
```

---

## Фаза 5: Метрики приложений

### Цель
Добавить Prometheus метрики во все сервисы.

### 5.1. Общий модуль метрик

**Файл:** `shared_models/src/shared_models/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge, Info
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# === Common Metrics ===

http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# === Assistant Service Metrics ===

llm_requests_total = Counter(
    'llm_requests_total',
    'Total LLM API requests',
    ['model', 'status']
)

llm_request_duration_seconds = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0]
)

llm_tokens_total = Counter(
    'llm_tokens_total',
    'Total tokens used',
    ['model', 'type']  # type: input, output
)

tool_calls_total = Counter(
    'tool_calls_total',
    'Total tool calls',
    ['tool_name', 'status']
)

messages_processed_total = Counter(
    'messages_processed_total',
    'Total messages processed',
    ['source', 'status']
)

# === Queue Metrics ===

queue_length = Gauge(
    'queue_length',
    'Current queue length',
    ['queue_name']
)

queue_messages_total = Counter(
    'queue_messages_total',
    'Total queue messages',
    ['queue_name', 'direction']  # direction: push, pop
)

# === Memory/RAG Metrics ===

memory_operations_total = Counter(
    'memory_operations_total',
    'Total memory operations',
    ['operation']  # save, retrieve, search
)

rag_search_duration_seconds = Histogram(
    'rag_search_duration_seconds',
    'RAG search duration',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)


def get_metrics():
    """Return metrics in Prometheus format."""
    return generate_latest()


def get_content_type():
    """Return Prometheus content type."""
    return CONTENT_TYPE_LATEST
```

### 5.2. FastAPI middleware для метрик

**Файл:** `shared_models/src/shared_models/metrics_middleware.py`

```python
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .metrics import http_requests_total, http_request_duration_seconds


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware для сбора HTTP метрик."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        duration = time.perf_counter() - start_time
        
        # Нормализуем endpoint (убираем параметры пути)
        endpoint = request.url.path
        # Заменяем UUID и числовые ID на плейсхолдеры
        import re
        endpoint = re.sub(r'/[0-9a-f-]{36}', '/{id}', endpoint)
        endpoint = re.sub(r'/\d+', '/{id}', endpoint)
        
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=endpoint
        ).observe(duration)
        
        return response
```

### 5.3. Добавление /metrics endpoint

**Для FastAPI сервисов (rest_service, rag_service, google_calendar_service):**

```python
from fastapi import Response
from shared_models.metrics import get_metrics, get_content_type
from shared_models.metrics_middleware import PrometheusMiddleware

app = FastAPI()
app.add_middleware(PrometheusMiddleware)

@app.get("/metrics")
async def metrics():
    return Response(
        content=get_metrics(),
        media_type=get_content_type()
    )
```

---

## Фаза 6: Расширение админки

### Цель
Добавить страницы для просмотра логов, джобов, памяти и очередей.

### 6.1. Структура новых страниц

```
admin_service/src/pages/
├── monitoring/
│   ├── __init__.py
│   ├── logs.py          # Просмотр логов (embed Grafana или Loki API)
│   ├── jobs.py          # История cron-джобов
│   ├── queues.py        # Состояние очередей
│   └── metrics.py       # Ключевые метрики (embed Grafana panels)
├── users/
│   ├── users.py
│   └── user_memory.py   # NEW: Память пользователя
└── ...
```

### 6.2. Страница просмотра памяти пользователя

**Файл:** `admin_service/src/pages/users/user_memory.py`

```python
import streamlit as st
from rest_client import RestServiceClient


def show_user_memory_page(rest_client: RestServiceClient, user_id: int):
    """Страница просмотра памяти пользователя."""
    st.header(f"Память пользователя #{user_id}")
    
    # Загружаем факты пользователя
    memories = rest_client.get(f"/memories/user/{user_id}")
    
    if not memories:
        st.info("У пользователя пока нет сохраненных фактов")
        return
    
    st.write(f"Всего фактов: {len(memories)}")
    
    # Фильтры
    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("Поиск по содержимому")
    with col2:
        sort_by = st.selectbox("Сортировка", ["Дата (новые)", "Дата (старые)"])
    
    # Фильтрация
    filtered = memories
    if search_query:
        filtered = [m for m in memories if search_query.lower() in m.get("content", "").lower()]
    
    # Сортировка
    reverse = sort_by == "Дата (новые)"
    filtered.sort(key=lambda x: x.get("created_at", ""), reverse=reverse)
    
    # Отображение
    for memory in filtered:
        with st.expander(f"Факт: {memory.get('content', '')[:100]}..."):
            st.write(f"**ID:** {memory.get('id')}")
            st.write(f"**Создан:** {memory.get('created_at')}")
            st.write(f"**Источник:** {memory.get('source', 'unknown')}")
            st.write("**Полное содержимое:**")
            st.text(memory.get("content", ""))
            
            # Кнопка удаления
            if st.button("Удалить", key=f"delete_{memory.get('id')}"):
                if rest_client.delete(f"/memories/{memory.get('id')}"):
                    st.success("Факт удален")
                    st.rerun()
```

### 6.3. Страница истории джобов

**Файл:** `admin_service/src/pages/monitoring/jobs.py`

```python
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from rest_client import RestServiceClient


def show_jobs_page(rest_client: RestServiceClient):
    """Страница мониторинга cron-джобов."""
    st.header("Cron Jobs")
    
    # Статистика
    stats = rest_client.get("/job-executions/stats?hours=24")
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Всего (24ч)", stats.get("total", 0))
        col2.metric("Успешных", stats.get("completed", 0))
        col3.metric("Ошибок", stats.get("failed", 0))
        col4.metric("Выполняются", stats.get("running", 0))
    
    st.divider()
    
    # Фильтры
    col1, col2, col3 = st.columns(3)
    with col1:
        job_type = st.selectbox(
            "Тип джоба",
            ["Все", "reminder", "memory_extraction", "update_reminders"]
        )
    with col2:
        status = st.selectbox(
            "Статус",
            ["Все", "scheduled", "running", "completed", "failed"]
        )
    with col3:
        hours = st.slider("Период (часов)", 1, 168, 24)
    
    # Параметры запроса
    params = {"hours": hours, "limit": 100}
    if job_type != "Все":
        params["job_type"] = job_type
    if status != "Все":
        params["status"] = status
    
    # Загружаем данные
    jobs = rest_client.get("/job-executions/", params=params)
    
    if not jobs:
        st.info("Нет данных за выбранный период")
        return
    
    # Таблица
    df = pd.DataFrame(jobs)
    df['scheduled_at'] = pd.to_datetime(df['scheduled_at'])
    df['duration_sec'] = df['duration_ms'].apply(
        lambda x: f"{x/1000:.2f}" if x else "-"
    )
    
    # Цветовая индикация статуса
    def highlight_status(row):
        if row['status'] == 'failed':
            return ['background-color: #ffcccc'] * len(row)
        elif row['status'] == 'running':
            return ['background-color: #ffffcc'] * len(row)
        elif row['status'] == 'completed':
            return ['background-color: #ccffcc'] * len(row)
        return [''] * len(row)
    
    styled_df = df[['job_name', 'job_type', 'status', 'scheduled_at', 'duration_sec', 'error']].style.apply(
        highlight_status, axis=1
    )
    
    st.dataframe(styled_df, use_container_width=True)
    
    # Детали выбранного джоба
    st.subheader("Детали")
    selected_id = st.selectbox(
        "Выберите джоб для просмотра деталей",
        options=[j['id'] for j in jobs],
        format_func=lambda x: next(
            (f"{j['job_name']} ({j['scheduled_at']})" for j in jobs if j['id'] == x),
            x
        )
    )
    
    if selected_id:
        job = next((j for j in jobs if j['id'] == selected_id), None)
        if job:
            st.json(job)
```

### 6.4. Страница состояния очередей

**Файл:** `admin_service/src/pages/monitoring/queues.py`

```python
import streamlit as st
import pandas as pd
from rest_client import RestServiceClient


def show_queues_page(rest_client: RestServiceClient):
    """Страница мониторинга очередей Redis."""
    st.header("Message Queues")
    
    # Текущее состояние
    current = rest_client.get("/queue-stats/current")
    if current:
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "TO_SECRETARY Queue",
                current.get("to_secretary", {}).get("length", 0),
                help="Сообщения ожидающие обработки ассистентом"
            )
        with col2:
            st.metric(
                "TO_TELEGRAM Queue", 
                current.get("to_telegram", {}).get("length", 0),
                help="Ответы ожидающие отправки в Telegram"
            )
    
    st.divider()
    
    # Статистика
    stats = rest_client.get("/queue-stats/")
    if stats:
        for queue_stat in stats:
            with st.expander(f"📊 {queue_stat['queue_name']}", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.metric("Всего", queue_stat['total_messages'])
                col2.metric("За час", queue_stat['messages_last_hour'])
                col3.metric("За 24ч", queue_stat['messages_last_24h'])
                
                if queue_stat.get('by_type'):
                    st.write("**По типу:**")
                    st.bar_chart(queue_stat['by_type'])
                
                if queue_stat.get('by_source'):
                    st.write("**По источнику:**")
                    st.bar_chart(queue_stat['by_source'])
    
    st.divider()
    
    # История сообщений
    st.subheader("История сообщений")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        queue_filter = st.selectbox("Очередь", ["Все", "to_secretary", "to_telegram"])
    with col2:
        user_filter = st.text_input("User ID")
    with col3:
        hours = st.slider("Период (часов)", 1, 48, 24)
    
    params = {"hours": hours, "limit": 50}
    if queue_filter != "Все":
        params["queue_name"] = queue_filter
    if user_filter:
        params["user_id"] = int(user_filter)
    
    messages = rest_client.get("/queue-stats/messages", params=params)
    
    if messages:
        for msg in messages:
            with st.expander(
                f"{msg['created_at']} | {msg['queue_name']} | {msg['message_type']}"
            ):
                st.write(f"**User ID:** {msg.get('user_id')}")
                st.write(f"**Correlation ID:** {msg.get('correlation_id')}")
                st.write(f"**Source:** {msg.get('source')}")
                st.json(msg.get('payload'))
    else:
        st.info("Нет сообщений за выбранный период")
```

### 6.5. Встраивание Grafana дашбордов

**Файл:** `admin_service/src/pages/monitoring/logs.py`

```python
import streamlit as st
from config.settings import settings


def show_logs_page():
    """Страница просмотра логов через встроенный Grafana."""
    st.header("Logs")
    
    # Фильтры для построения URL
    col1, col2, col3 = st.columns(3)
    with col1:
        service = st.selectbox(
            "Service",
            ["all", "assistant_service", "rest_service", "telegram_bot_service", 
             "cron_service", "google_calendar_service", "rag_service"]
        )
    with col2:
        level = st.selectbox("Level", ["all", "error", "warning", "info", "debug"])
    with col3:
        time_range = st.selectbox(
            "Time Range",
            ["Last 15 minutes", "Last 1 hour", "Last 6 hours", "Last 24 hours"]
        )
    
    # Строим LogQL query
    filters = []
    if service != "all":
        filters.append(f'service="{service}"')
    if level != "all":
        filters.append(f'level="{level}"')
    
    logql = "{" + ",".join(filters) + "}" if filters else '{job="docker"}'
    
    # Time range mapping
    time_map = {
        "Last 15 minutes": "15m",
        "Last 1 hour": "1h", 
        "Last 6 hours": "6h",
        "Last 24 hours": "24h",
    }
    
    # Grafana Explore URL
    grafana_url = settings.GRAFANA_URL or "http://localhost:3000"
    explore_url = (
        f"{grafana_url}/explore?"
        f"orgId=1&"
        f"left=%7B%22datasource%22:%22Loki%22,"
        f"%22queries%22:%5B%7B%22expr%22:%22{logql}%22%7D%5D,"
        f"%22range%22:%7B%22from%22:%22now-{time_map[time_range]}%22,"
        f"%22to%22:%22now%22%7D%7D"
    )
    
    st.markdown(f"[Открыть в Grafana Explore]({explore_url})")
    
    # Встраиваем iframe (требует настройки allow_embedding в Grafana)
    st.components.v1.iframe(
        explore_url,
        height=800,
        scrolling=True
    )
```

### 6.6. Обновление навигации

**Обновить `admin_service/src/config/settings.py`:**

```python
NAV_ITEMS: list[str] = [
    "Users",
    "Assistants", 
    "Tools",
    "Global Settings",
    "---",  # Разделитель
    "Logs",
    "Jobs",
    "Queues",
    "Metrics",
]
```

---

## Фаза 7: Алертинг

### Цель
Настроить алерты для критических ошибок с отправкой в Telegram.

### 7.1. Grafana Contact Points

**Файл:** `monitoring/grafana/provisioning/alerting/alerting.yml`

```yaml
apiVersion: 1

contactPoints:
  - orgId: 1
    name: telegram-alerts
    receivers:
      - uid: telegram-bot
        type: telegram
        settings:
          # Configure via environment variables (see .env section below)
          message: |
            🚨 *Alert: {{ .CommonLabels.alertname }}*
            
            Status: {{ .Status }}
            Service: {{ .CommonLabels.service }}
            
            {{ range .Alerts }}
            Summary: {{ .Annotations.summary }}
            Description: {{ .Annotations.description }}
            {{ end }}
            
            [View in Grafana]({{ .ExternalURL }})

policies:
  - orgId: 1
    receiver: telegram-alerts
    group_by: ['alertname', 'service']
    group_wait: 30s
    group_interval: 5m
    repeat_interval: 4h
```

### 7.2. Alert Rules

**Файл:** `monitoring/grafana/provisioning/alerting/rules.yml`

```yaml
apiVersion: 1

groups:
  - orgId: 1
    name: Smart Assistant Alerts
    folder: Smart Assistant
    interval: 1m
    rules:
      # High Error Rate
      - uid: high-error-rate
        title: High Error Rate
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: loki
            model:
              expr: 'sum(count_over_time({level="error"}[5m]))'
          - refId: B
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: loki
            model:
              expr: 'sum(count_over_time({level=~".+"}[5m]))'
          - refId: C
            datasourceUid: __expr__
            model:
              expression: "$A / $B > 0.1"
              type: math
        for: 5m
        annotations:
          summary: "High error rate detected"
          description: "Error rate is above 10% in the last 5 minutes"
        labels:
          severity: critical

      # Service Down
      - uid: service-down
        title: Service Down
        condition: A
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'up{job=~"rest_service|assistant_service|telegram_bot_service"} == 0'
        for: 2m
        annotations:
          summary: "Service {{ $labels.job }} is down"
          description: "Service has been unreachable for more than 2 minutes"
        labels:
          severity: critical

      # Job Failures
      - uid: job-failures
        title: Cron Job Failures
        condition: A
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'increase(cron_jobs_total{status="failed"}[1h]) > 5'
        for: 0m
        annotations:
          summary: "Multiple cron job failures"
          description: "More than 5 job failures in the last hour"
        labels:
          severity: warning

      # Queue Backlog
      - uid: queue-backlog
        title: Queue Backlog Growing
        condition: A
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'queue_length{queue_name="to_secretary"} > 100'
        for: 10m
        annotations:
          summary: "Message queue backlog"
          description: "Queue {{ $labels.queue_name }} has more than 100 pending messages"
        labels:
          severity: warning

      # LLM API Errors
      - uid: llm-errors
        title: LLM API Errors
        condition: A
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'increase(llm_requests_total{status="error"}[5m]) > 10'
        for: 0m
        annotations:
          summary: "LLM API errors detected"
          description: "More than 10 LLM API errors in the last 5 minutes"
        labels:
          severity: critical

      # Database Connection Issues
      - uid: db-connection
        title: Database Connection Issues
        condition: A
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'pg_up == 0'
        for: 1m
        annotations:
          summary: "PostgreSQL connection lost"
          description: "Cannot connect to PostgreSQL database"
        labels:
          severity: critical

      # Redis Connection Issues
      - uid: redis-connection
        title: Redis Connection Issues
        condition: A
        data:
          - refId: A
            datasourceUid: prometheus
            model:
              expr: 'redis_up == 0'
        for: 1m
        annotations:
          summary: "Redis connection lost"
          description: "Cannot connect to Redis"
        labels:
          severity: critical
```

### 7.3. Переменные окружения для алертинга

Добавить в `.env`:

Configure Telegram alerting credentials via environment variables.

---

## Конфигурация и переменные окружения

### Новые переменные в .env

```bash
# === Monitoring ===
# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PW=<set-secure-value>
GRAFANA_ROOT_URL=http://localhost:3000

# Alerting via Telegram
# Set your Telegram bot credentials here

# Log retention (Loki)
LOG_RETENTION_HOURS=48

# Metrics retention (Prometheus)
METRICS_RETENTION_HOURS=48
```

### Обновление settings в сервисах

```python
# shared_models/src/shared_models/config.py
from pydantic_settings import BaseSettings


class MonitoringSettings(BaseSettings):
    """Настройки мониторинга."""
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = True  # False для dev
    
    # Metrics
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 8080
    
    # Grafana (для админки)
    GRAFANA_URL: str = "http://grafana:3000"
    
    class Config:
        env_prefix = ""
```

---

## Чеклист внедрения

### Фаза 1: Стандартизация логирования ✅ ЗАВЕРШЕНО
- [x] Создать `shared_models/src/shared_models/logging.py`
- [x] Обновить `shared_models/pyproject.toml` (добавить structlog)
- [x] Мигрировать rest_service на новый логгер
- [x] Мигрировать assistant_service
- [x] Мигрировать telegram_bot_service
- [x] Мигрировать cron_service (перейти с logging на structlog)
- [x] Мигрировать google_calendar_service
- [x] Мигрировать rag_service
- [x] Мигрировать admin_service
- [x] Удалить старые logger.py файлы
- [x] Добавить correlation_id в REST middleware
- [ ] Тесты логирования

### Фаза 2: Инфраструктура мониторинга ✅ ЗАВЕРШЕНО
- [x] Создать директорию `monitoring/`
- [x] Создать `docker-compose.monitoring.yml`
- [x] Создать конфиг Loki
- [x] Создать конфиг Promtail
- [x] Создать конфиг Prometheus
- [x] Создать provisioning для Grafana (с uid для datasources)
- [x] Добавить redis_exporter в docker-compose.yml
- [x] Добавить postgres_exporter в docker-compose.yml
- [x] Создать базовые дашборды Grafana (overview.json, logs.json)
- [x] Создать README для monitoring/
- [ ] Протестировать сбор логов
- [ ] Протестировать сбор метрик

### Фаза 3: Инструментирование cron_service ✅ ЗАВЕРШЕНО
- [x] Создать модель JobExecution (`rest_service/src/models/job_execution.py`)
- [x] Создать миграцию Alembic (`20251214_200000_add_job_executions_table.py`)
- [x] Создать CRUD для job_executions
- [x] Создать API endpoints (`/api/job-executions/`)
- [x] Обновить scheduler.py для записи истории
- [x] Добавить Prometheus метрики (`cron_service/src/metrics.py`)
- [x] Добавить HTTP сервер для метрик (порт 8080)
- [x] Обновить docker-compose.yml (порт 8080, healthcheck)
- [ ] Тесты

### Фаза 4: Observability очередей ✅ ЗАВЕРШЕНО
- [x] Создать модель QueueMessageLog
- [x] Создать миграцию Alembic
- [x] Создать API endpoints для статистики
- [x] Добавить логирование в assistant_service
- [x] Добавить логирование в telegram_bot_service
- [ ] Тесты

### Фаза 5: Метрики приложений ✅ ЗАВЕРШЕНО
- [x] Создать локальные metrics.py в каждом сервисе (prometheus-client)
- [x] Создать middleware для FastAPI (rest_service, rag_service, google_calendar_service)
- [x] Добавить /metrics в rest_service
- [x] Добавить /metrics в rag_service
- [x] Добавить /metrics в google_calendar_service
- [x] Добавить metrics server в telegram_bot_service (порт 8080)
- [x] Добавить metrics server в assistant_service (порт 8080)
- [x] Обновить Prometheus config (добавить telegram_bot_service, google_calendar_service)
- [x] Обновить healthcheck в docker-compose.yml для assistant/telegram
- [ ] Тесты

### Фаза 6: Расширение админки ✅ ЗАВЕРШЕНО
- [x] Создать страницу user_memory.py
- [x] Создать страницу jobs.py
- [x] Создать страницу queues.py
- [x] Создать страницу logs.py (с embed Grafana)
- [x] Создать страницу metrics.py
- [x] Обновить навигацию
- [x] Добавить REST client методы (get_job_executions, get_job_stats, get_queue_stats, get_queue_messages, get_user_memories, delete_memory)
- [x] Добавить настройки GRAFANA_URL, PROMETHEUS_URL, LOKI_URL
- [ ] Настроить Grafana allow_embedding
- [ ] Тесты

### Фаза 7: Алертинг ✅ ЗАВЕРШЕНО
- [x] Создать contact points конфиг (`monitoring/grafana/provisioning/alerting/contactpoints.yml`)
- [x] Создать notification policies (`monitoring/grafana/provisioning/alerting/policies.yml`)
- [x] Создать alert rules (`monitoring/grafana/provisioning/alerting/rules.yml`)
- [x] Добавить env переменные TELEGRAM_ALERT_BOT_TOKEN, TELEGRAM_ALERT_CHAT_ID
- [x] Документация по алертам в README
- [ ] Протестировать алерты (требует настройки Telegram бота)

---

## Timeline (оценка)

| Фаза | Сложность | Оценка времени |
|------|-----------|----------------|
| 1. Логирование | Средняя | 2-3 дня |
| 2. Инфраструктура | Средняя | 2-3 дня |
| 3. Cron jobs | Средняя | 2-3 дня |
| 4. Очереди | Низкая | 1-2 дня |
| 5. Метрики | Средняя | 2-3 дня |
| 6. Админка | Средняя | 2-3 дня |
| 7. Алертинг | Низкая | 1 день |

**Итого: ~12-18 рабочих дней**

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Увеличение нагрузки от логирования | Средняя | Sampling для debug логов, rate limiting |
| Место на диске для логов | Высокая | Retention 48h, compaction в Loki |
| Сложность отладки Promtail | Средняя | Подробная документация, готовые конфиги |
| Перформанс админки с embed | Низкая | Lazy loading, кэширование |
| Спам алертов | Средняя | Правильные thresholds, grouping, repeat_interval |

---

## Ссылки

- [Grafana Loki Documentation](https://grafana.com/docs/loki/latest/)
- [Promtail Configuration](https://grafana.com/docs/loki/latest/clients/promtail/configuration/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Alerting](https://grafana.com/docs/grafana/latest/alerting/)
- [structlog Documentation](https://www.structlog.org/en/stable/)
