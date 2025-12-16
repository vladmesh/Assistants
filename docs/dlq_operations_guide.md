# DLQ Operations Guide

Руководство по эксплуатации Dead Letter Queue (DLQ) в Smart Assistant.

## Обзор

DLQ используется для хранения сообщений, которые не удалось обработать после нескольких попыток. Это позволяет:
- Не терять сообщения при ошибках
- Анализировать причины сбоев
- Восстанавливать сообщения после исправления проблем

## Архитектура

```
Input Queue                    DLQ Stream
(to_secretary)                (to_secretary:dlq)
     │                              ▲
     │ read                         │ send_to_dlq
     ▼                              │
┌─────────────┐    error      ┌─────┴─────┐
│ Orchestrator│──────────────▶│  Retry    │
│             │               │  Logic    │
└──────┬──────┘               └───────────┘
       │ success                    │
       │                            │ retry_count >= 3
       ▼                            ▼
   ACK message              Move to DLQ + ACK
```

## Мониторинг

### Grafana Dashboard

Панели DLQ находятся в дашборде "Smart Assistant Overview":
- **DLQ Size** — текущее количество сообщений в DLQ
- **DLQ Growth Rate** — скорость поступления в DLQ (msg/5min)
- **Retry Rate** — количество retry попыток
- **Errors by Type** — распределение ошибок по типам

### Prometheus метрики

```promql
# Текущий размер DLQ
dlq_size{queue="to_secretary"}

# Rate сообщений в DLQ за последние 5 минут
rate(messages_dlq_total[5m])

# Топ типов ошибок
topk(5, sum by (error_type) (messages_dlq_total))

# Retry rate
rate(message_processing_retries_total[5m])
```

### Алерты

| Alert | Условие | Severity | Действие |
|-------|---------|----------|----------|
| DLQSizeHigh | dlq_size > 10 (5 мин) | warning | Проверить логи, разобрать ошибки |
| DLQGrowthRapid | increase(messages_dlq_total[5m]) > 10 | critical | Срочно проверить сервисы |

## Разбор ошибок

### 1. Получить список сообщений в DLQ

```bash
# Все сообщения
curl "http://localhost:8000/api/dlq/messages?queue=to_secretary"

# Фильтр по типу ошибки
curl "http://localhost:8000/api/dlq/messages?queue=to_secretary&error_type=ValueError"

# Фильтр по пользователю
curl "http://localhost:8000/api/dlq/messages?queue=to_secretary&user_id=123"
```

### 2. Получить статистику DLQ

```bash
curl "http://localhost:8000/api/dlq/stats?queue=to_secretary"
```

Пример ответа:
```json
{
  "queue_name": "to_secretary",
  "total_messages": 5,
  "by_error_type": {
    "ConnectionError": 3,
    "ValueError": 2
  },
  "oldest_message_at": "2024-12-16T10:00:00Z",
  "newest_message_at": "2024-12-16T12:30:00Z"
}
```

### 3. Анализ конкретного сообщения

Каждое сообщение в DLQ содержит:
- `message_id` — ID в DLQ stream
- `original_message_id` — оригинальный ID сообщения
- `payload` — тело сообщения (JSON)
- `error_type` — тип исключения
- `error_message` — текст ошибки
- `retry_count` — количество попыток
- `failed_at` — время последней ошибки
- `user_id` — ID пользователя

## Восстановление сообщений

### Retry одного сообщения

```bash
curl -X POST "http://localhost:8000/api/dlq/messages/{message_id}/retry?queue=to_secretary"
```

Сообщение будет:
1. Извлечено из DLQ
2. Добавлено обратно в основную очередь
3. Удалено из DLQ

### Массовый retry (после исправления бага)

```bash
# Получить все сообщения определенного типа ошибки
messages=$(curl -s "http://localhost:8000/api/dlq/messages?queue=to_secretary&error_type=ConnectionError" | jq -r '.[].message_id')

# Retry каждого
for msg_id in $messages; do
  curl -X POST "http://localhost:8000/api/dlq/messages/$msg_id/retry?queue=to_secretary"
  echo "Retried: $msg_id"
done
```

## Очистка DLQ

### Удаление одного сообщения

После ручного разбора (например, дубликат или невалидные данные):

```bash
curl -X DELETE "http://localhost:8000/api/dlq/messages/{message_id}?queue=to_secretary"
```

### Очистка по типу ошибки

```bash
curl -X DELETE "http://localhost:8000/api/dlq/messages?queue=to_secretary&error_type=ValidationError"
```

### Полная очистка DLQ

⚠️ **ОСТОРОЖНО**: Это удалит все сообщения без возможности восстановления!

```bash
curl -X DELETE "http://localhost:8000/api/dlq/messages?queue=to_secretary"
```

## Типичные сценарии

### Сценарий 1: Временный сбой внешнего сервиса

**Симптомы**: Много `ConnectionError` или `TimeoutError` в DLQ

**Действия**:
1. Проверить статус внешних сервисов (REST API, Redis, OpenAI)
2. Дождаться восстановления
3. Массовый retry всех сообщений с этим типом ошибки

### Сценарий 2: Баг в обработке

**Симптомы**: `ValueError`, `KeyError`, `AttributeError` в DLQ

**Действия**:
1. Проанализировать payload сообщений
2. Исправить баг в коде
3. Задеплоить исправление
4. Retry сообщений

### Сценарий 3: Невалидные входные данные

**Симптомы**: `ValidationError` в DLQ

**Действия**:
1. Проанализировать payload — понять источник невалидных данных
2. Исправить источник (Telegram bot, cron service)
3. Удалить невалидные сообщения из DLQ (они не могут быть обработаны)

## Redis CLI

Для прямого доступа к DLQ через Redis:

```bash
# Подключение
docker exec -it assistants-redis-1 redis-cli

# Размер DLQ
XLEN to_secretary:dlq

# Последние 10 сообщений
XRANGE to_secretary:dlq - + COUNT 10

# Все сообщения (осторожно при большом размере)
XRANGE to_secretary:dlq - +

# Информация о consumer group основной очереди
XINFO GROUPS to_secretary
XINFO CONSUMERS to_secretary assistant_group

# Pending сообщения (в процессе retry)
XPENDING to_secretary assistant_group
```

## Troubleshooting

### DLQ растет слишком быстро

1. Проверить логи assistant_service на ошибки
2. Проверить статус зависимых сервисов
3. Проверить метрики circuit breaker
4. Временно увеличить MAX_RETRIES если это временный сбой

### Сообщения не обрабатываются повторно

1. Проверить что `xautoclaim` работает (idle_reclaim_ms=60000)
2. Проверить consumer group: `XINFO CONSUMERS to_secretary assistant_group`
3. Проверить pending messages: `XPENDING to_secretary assistant_group`

### REST API DLQ возвращает 503

Redis недоступен. Проверить:
1. Статус Redis контейнера
2. Сетевое соединение между rest_service и Redis
3. Настройки REDIS_HOST/PORT/DB в переменных окружения
