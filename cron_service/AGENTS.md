# Cron Service Detailed Overview (Updated for Reminder Service)

## 1. Overview
- **Purpose:** Executes scheduled reminders managed via `rest_service`. 
- **Functions:** 
  - Periodically fetches active reminder configurations from the `/api/reminders/scheduled` endpoint of `rest_service`.
  - Schedules one-time (`DateTrigger`) and recurring (`CronTrigger`) reminders using APScheduler.
  - Sends `reminder_triggered` events to a Redis queue upon execution.
  - Marks completed one-time reminders via `rest_service` API (`PATCH /api/reminders/{id}`).
- **Tech Stack:** 
  - Python with APScheduler
  - Redis for message queuing (`queue:to_secretary`)
  - REST API integration (`rest_service`)
  - Dockerized microservice architecture

## 2. Directory Structure
```
cron_service/
├── src/
│   ├── main.py              # Service entry point
│   ├── scheduler.py         # Core scheduling logic (APScheduler, job loading)
│   ├── redis_client.py      # Redis integration (sending trigger events)
│   └── rest_client.py       # REST API integration (fetching reminders, marking complete)
└── tests/                  # Test suite
    ├── conftest.py         # Test fixtures
    ├── test_scheduler.py   # Scheduler tests
    └── .env.test           # Test environment config
```

## 3. Key Components

### 3.1 Scheduler (`scheduler.py`)
```python
scheduler = BackgroundScheduler(timezone=utc)

def start_scheduler():
    """Запускает планировщик задач."""
    try:
        scheduler.add_job(
            update_jobs_from_rest, # Renamed from update_jobs_from_rest
            "interval",
            minutes=1,
            id="update_reminders_from_rest" # Changed ID
        )
        scheduler.start()

def schedule_job(reminder):
    """Schedules or updates a single reminder job."""
    # Uses DateTrigger for one_time, CronTrigger for recurring
    # Calls _job_func on trigger

def _job_func(reminder_data):
    """Function executed by the scheduler."""
    send_reminder_trigger(reminder_data)
    if reminder_data['type'] == 'one_time':
        mark_reminder_completed(reminder_data['id'])
```
- **Features:**
  - Background scheduling with APScheduler (UTC timezone).
  - Automatic job updates from `rest_service` every minute via `update_jobs_from_rest`.
  - Handles `one_time` (DateTrigger) and `recurring` (CronTrigger) reminders.
  - Calls `_job_func` which sends Redis event and marks one-time jobs as complete via REST API.
  - Error handling and logging.

### 3.2 Redis Client (`redis_client.py`)
```python
def send_reminder_trigger(reminder_data: dict) -> None:
    """Sends a reminder trigger event to the assistant via Redis."""
    message = {
        "assistant_id": reminder_data["assistant_id"], # Included for potential future use/audit
        "event": "reminder_triggered",
        "payload": {
            "reminder_id": reminder_data["id"],
            "user_id": reminder_data["user_id"],
            "reminder_type": reminder_data["type"],
            "payload": json.loads(reminder_data["payload"]), # Inner payload
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "created_at": reminder_data["created_at"],
        },
    }
    message_json = json.dumps(message, default=str)
    redis_client.rpush(OUTPUT_QUEUE, message_json)
```
- **Features:**
  - Sends structured JSON `reminder_triggered` events.
  - Uses `OUTPUT_QUEUE` (configured via `REDIS_QUEUE_TO_SECRETARY` env var).
  - Error handling during message creation/sending.

### 3.3 REST Client (`rest_client.py`)
```python
def fetch_active_reminders():
    """Fetches the list of active reminders from the REST service."""
    url = f"{REST_SERVICE_URL}/api/reminders/scheduled"
    response = requests.get(url, timeout=10)
    # ... error handling ...
    return response.json()

def mark_reminder_completed(reminder_id: UUID) -> bool:
    """Marks a reminder as completed via the REST service."""
    url = f"{REST_SERVICE_URL}/api/reminders/{reminder_id}"
    payload = {"status": "completed"}
    response = requests.patch(url, json=payload, timeout=10)
    # ... error handling ...
    return response.status_code == 200
```
- **Features:**
  - Fetches active reminders from `/api/reminders/scheduled`.
  - Updates one-time reminder status via `PATCH /api/reminders/{id}`.
  - Error handling and retries (implicitly via `update_jobs_from_rest`).
  - Logging.

## 4. Configuration

### 4.1 Environment Variables
```python
# Redis settings
REDIS_HOST=os.getenv("REDIS_HOST")
REDIS_PORT=int(os.getenv("REDIS_PORT"))
REDIS_DB=int(os.getenv("REDIS_DB"))
# Queue where reminder events are sent (read by assistant_service)
OUTPUT_QUEUE=os.getenv("REDIS_QUEUE_TO_SECRETARY") 

# REST service settings
REST_SERVICE_URL=os.getenv("REST_SERVICE_URL")

# Scheduler settings (Defaults removed where applicable)
MAX_RETRIES = 3 # For fetching jobs
RETRY_DELAY = 5  # seconds
```
- **Note:** `CHAT_ID` is no longer directly used by this service for notifications.

## 5. Job Management

### 5.1 Reminder Loading (`scheduler.py`)
- `update_jobs_from_rest` fetches from `/api/reminders/scheduled`.
- Iterates through reminders, calls `schedule_job` for each.
- Removes jobs from APScheduler that are no longer active in the REST service response.

### 5.2 Job Scheduling (`scheduler.py`)
- `schedule_job` determines `DateTrigger` (from `trigger_at`) or `CronTrigger` (from `cron_expression`).
- Sets `_job_func` as the callback with reminder data as argument.
- Handles job updates/rescheduling via APScheduler's `add_job` (with `replace_existing=True` implicitly or `reschedule_job`).

### 5.3 Job Execution (`scheduler.py`)
- `_job_func` is called by APScheduler.
- Calls `send_reminder_trigger` to notify `assistant_service`.
- Calls `mark_reminder_completed` for `one_time` reminders.

## 6. Testing

### 6.1 Test Structure
- **Unit Tests:**
  - Trigger creation logic (`DateTrigger`, `CronTrigger`).
  - `reminder_triggered` event formatting (`redis_client.py`).
  - REST client calls (`rest_client.py`).
- **Integration Tests:** (More relevant now)
  - Full flow: Fetch -> Schedule -> Trigger -> Redis Event -> Mark Complete.
  - Mocking `requests` and `redis`.

### 6.2 Test Environment
```python
# conftest.py (Example)
@pytest.fixture
def mock_redis(mocker):
    # Spy or mock redis_client.rpush
    spy = mocker.spy(redis_client, "rpush") 
    yield spy

@pytest.fixture
def mock_rest_client(mocker):
    # Mock requests.get and requests.patch
    mock_get = mocker.patch("src.rest_client.requests.get")
    mock_patch = mocker.patch("src.rest_client.requests.patch")
    yield mock_get, mock_patch
```

## 7. Integration

### 7.1 REST API Integration
- **Reads:** Active reminders (`GET /api/reminders/scheduled`).
- **Writes:** Updates reminder status to 'completed' (`PATCH /api/reminders/{id}`).

### 7.2 Redis Integration
- **Writes:** Sends `reminder_triggered` events to `REDIS_QUEUE_TO_SECRETARY`.

## 8. Best Practices

### 8.1 Development Guidelines
- Use type hints
- Follow naming conventions
- Document changes
- Maintain test coverage

### 8.2 Error Handling
- Structured logging
- Retry mechanisms (for REST calls within `update_jobs_from_rest`)
- Graceful degradation
- Error reporting

### 8.3 Performance
- Connection pooling (handled by `redis-py` and potentially `requests.Session`)
- Efficient scheduling (APScheduler handles this)
- Resource management
- Monitoring
