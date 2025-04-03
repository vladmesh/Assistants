# Cron Service Detailed Overview

## 1. Overview
- **Purpose:** Manages and executes scheduled tasks.
- **Functions:** 
  - Periodically fetches job configurations from REST API
  - Parses and validates CRON expressions
  - Executes scheduled tasks
  - Sends notifications via Redis
- **Tech Stack:** 
  - Python with APScheduler
  - Redis for message queuing
  - REST API integration
  - Dockerized microservice architecture

## 2. Directory Structure
```
cron_service/
├── src/
│   ├── main.py              # Service entry point
│   ├── scheduler.py         # Core scheduling logic
│   ├── redis_client.py      # Redis integration
│   └── rest_client.py       # REST API integration
└── tests/                  # Test suite
    ├── conftest.py         # Test fixtures
    ├── test_scheduler.py   # Scheduler tests
    └── .env.test           # Test environment config
```

## 3. Key Components

### 3.1 Scheduler
```python
scheduler = BackgroundScheduler(timezone=utc)

def start_scheduler():
    """Запускает планировщик задач."""
    try:
        scheduler.add_job(
            update_jobs_from_rest,
            "interval",
            minutes=1,
            id="update_jobs_from_rest"
        )
        scheduler.start()
```

- **Features:**
  - Background scheduling with APScheduler
  - UTC timezone support
  - Automatic job updates
  - Error handling and logging
  - Graceful shutdown

### 3.2 Redis Client
```python
def send_notification(chat_id: int, message: str, priority: str = "normal") -> None:
    """Отправляет уведомление через Redis."""
    data = {
        "chat_id": chat_id,
        "response": message,
        "status": "success"
    }
    redis_client.rpush(OUTPUT_QUEUE, json.dumps(data))
```

- **Features:**
  - Message queuing
  - Priority levels
  - Error handling
  - Connection pooling

### 3.3 REST Client
```python
def fetch_scheduled_jobs():
    """Получает список запланированных задач от REST-сервиса."""
    url = f"{REST_SERVICE_URL}/api/cronjobs/"
    response = requests.get(url)
    return response.json()
```

- **Features:**
  - Job configuration retrieval
  - Error handling
  - Automatic retries
  - Logging

## 4. Configuration

### 4.1 Environment Variables
```python
# Redis settings
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
OUTPUT_QUEUE = os.getenv("REDIS_QUEUE_TO_TELEGRAM", "queue:to_telegram")

# REST service settings
REST_SERVICE_URL = os.getenv("REST_SERVICE_URL", "http://rest_service:8000")

# Scheduler settings
CHAT_ID = int(os.getenv("TELEGRAM_ID", "0"))
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
```

## 5. Job Management

### 5.1 CRON Expression Parsing
```python
def parse_cron_expression(expression: str) -> dict:
    """Парсит CRON выражение и возвращает словарь с параметрами."""
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError("Invalid CRON expression")
    
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
        "timezone": utc
    }
```

### 5.2 Job Execution
- Automatic job updates every minute
- CRON expression validation
- Error handling and retries
- Status tracking

## 6. Testing

### 6.1 Test Structure
- **Unit Tests:**
  - CRON expression parsing
  - Job scheduling
  - Notification sending
  - REST API integration

### 6.2 Test Environment
```python
# conftest.py
@pytest.fixture
def mock_redis():
    with patch('redis_client.redis_client') as mock:
        yield mock

@pytest.fixture
def mock_rest():
    with patch('rest_client.requests') as mock:
        yield mock
```

## 7. Integration

### 7.1 REST API Integration
- Fetches job configurations
- Updates job status
- Handles errors and retries

### 7.2 Redis Integration
- Sends notifications
- Queues messages
- Handles connection issues

## 8. Best Practices

### 8.1 Development Guidelines
- Use type hints
- Follow naming conventions
- Document changes
- Maintain test coverage

### 8.2 Error Handling
- Structured logging
- Retry mechanisms
- Graceful degradation
- Error reporting

### 8.3 Performance
- Connection pooling
- Efficient scheduling
- Resource management
- Monitoring
