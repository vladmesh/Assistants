# Telegram Bot Service Detailed Overview

## 1. Overview
- **Purpose:** Provides an interactive interface for end users via Telegram
- **Functions:**
  - Receives and processes user messages
  - Identifies users through integration with the REST API
  - Sends formatted responses and notifications
- **Tech Stack:** Python (aiohttp, asyncio), Telegram Bot API, Dockerized microservice architecture

## 2. Directory Structure
```
telegram_bot_service/
├── src/
│   ├── bot/                     # Core bot logic (polling, dispatcher, lifecycle)
│   │   ├── polling.py           # Long-polling and update retrieval
│   │   ├── dispatcher.py        # Update routing to handlers
│   │   ├── lifecycle.py         # Bot startup, shutdown, task management
│   │   └── __init__.py
│   ├── handlers/                # Command, message, callback handlers
│   │   ├── command_start.py     # /start command handler
│   │   ├── command_select_secretary.py # Secretary selection callback handler
│   │   ├── message_text.py      # Text message handler
│   │   ├── callback_query.py    # Generic callback query handler
│   │   └── __init__.py
│   ├── services/                # Business logic and external interactions
│   │   ├── response_processor.py # Processes responses from assistant queue
│   │   ├── user_service.py       # User/secretary related logic (via REST)
│   │   ├── message_queue.py     # Handles sending messages to Redis queue
│   │   └── __init__.py
│   ├── clients/                 # Clients for external APIs (Renamed from client)
│   │   ├── telegram.py          # Telegram Bot API client
│   │   ├── rest.py              # REST API client
│   │   └── __init__.py
│   ├── config/                  # Configuration
│   │   ├── settings.py          # Pydantic settings
│   │   ├── logging_config.py    # (Optional) Logging setup
│   │   └── __init__.py
│   ├── keyboards/               # Inline keyboard factories
│   │   └── secretary_selection.py # Keyboard for secretary selection
│   │   └── __init__.py
│   ├── utils/                   # Utility functions
│   │   └── __init__.py
│   ├── main.py                  # Entry point: Initializes and runs the bot lifecycle
│   └── __init__.py
├── tests/                 # Test suite
│   ├── test_smoke.py     # Basic functionality tests
│   └── .env.test         # Test environment configuration
└── Dockerfile            # Container configuration
```

## 3. Key Components

### 3.1 Telegram Client (`clients/telegram.py`)
```python
class TelegramClient:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{settings.telegram_token}"
        self.session: Optional[aiohttp.ClientSession] = None
```

- Handles communication with Telegram Bot API
- Implements message sending and update retrieval
- Uses aiohttp for async HTTP requests
- Includes error handling and logging

### 3.2 REST Client (`clients/rest.py`)
```python
class RestClient:
    def __init__(self):
        self.base_url = settings.rest_service_url
        self.api_prefix = "/api"
```

- Manages communication with REST API service
- Handles user management, secretary assignment, and other API interactions.
- Implements methods like `get_or_create_user`, `get_user_secretary`, `set_user_secretary`, `list_secretaries`, `ping`.
- Includes error handling (e.g., raising `RestClientError`) and logging.

### 3.3 Response Processor (`services/response_processor.py`)
```python
async def handle_assistant_responses(
    telegram: TelegramClient, redis: aioredis.Redis
) -> None:
    """Handle responses from assistant service."""
```

- Processes responses from assistant service
- Listens to the assistant's output Redis queue (`assistant_output_queue`).
- Parses `AssistantResponseMessage`.
- Retrieves user's `chat_id` via `RestClient`.
- Sends the response or error message back to the user via `TelegramClient`.
- Runs as a background task managed by `BotLifecycle`.

### 3.4 Bot Lifecycle (`bot/lifecycle.py`)
```python
class BotLifecycle:
    async def run(self) -> None:
        # ... initialization, task creation, signal handling ...
```
- Manages the bot's startup sequence: initializes clients (`TelegramClient`, `RestClient`, `Redis`), creates `aiohttp` sessions.
- Starts and manages background tasks: polling (`run_polling`) and response processing (`handle_assistant_responses`).
- Sets up signal handlers for graceful shutdown (SIGINT, SIGTERM).
- Handles closing client sessions and stopping tasks during shutdown.
- Contains the main `run_bot()` entry point called by `main.py`.

### 3.5 Polling (`bot/polling.py`)
```python
async def run_polling(
    telegram: TelegramClient,
    rest: RestClient,
    stop_event: asyncio.Event,
    dispatcher_callback: Callable[..., Any],
) -> None:
```
- Runs the main loop to fetch updates from Telegram API using long polling (`telegram.get_updates`).
- Keeps track of the `last_update_id`.
- Passes received updates to the `dispatcher_callback` (`dispatch_update` from `dispatcher.py`) for further processing.
- Runs as a background task managed by `BotLifecycle`.
- Handles graceful shutdown via `stop_event`.

### 3.6 Dispatcher (`bot/dispatcher.py`)
```python
async def dispatch_update(
    update: Dict[str, Any], telegram: TelegramClient, rest: RestClient
) -> None:
```
- Receives updates from `run_polling`.
- Determines the update type (`message` or `callback_query`).
- Parses essential information (chat_id, user_id, text, data, etc.).
- Routes the update and context to the appropriate handler function in the `handlers/` directory (e.g., `command_start.handle_start`, `message_text.handle_text_message`).

### 3.7 Handlers (`handlers/`)
- Contains modules for handling specific types of user interactions:
  - `command_start.py`: Handles the `/start` command.
  - `message_text.py`: Handles regular text messages.
  - `command_select_secretary.py`: Handles the callback query for secretary selection.
  - `callback_query.py`: Handles other (currently unhandled) callback queries.
- Handlers receive context (clients, update details) from the dispatcher.
- Interact with services (`user_service`, `message_queue`) and clients (`TelegramClient`) to perform actions.
- Utilize keyboard factories (`keyboards/`) to generate UI elements.

### 3.8 User Service (`services/user_service.py`)
```python
async def get_or_create_telegram_user(rest: RestClient, ...) -> TelegramUserRead:
async def get_user_by_telegram_id(rest: RestClient, ...) -> Optional[TelegramUserRead]:
async def get_assigned_secretary(rest: RestClient, ...) -> Optional[AssistantRead]:
async def set_user_secretary(rest: RestClient, ...) -> None:
async def list_available_secretaries(rest: RestClient, ...) -> List[AssistantRead]:
```
- Provides an abstraction layer over `RestClient` for user and secretary related operations.
- Called by handlers to get/create users, check/set secretary assignments, and list available secretaries.
- Simplifies the logic within handlers.

### 3.9 Message Queue Service (`services/message_queue.py`)
```python
async def send_message_to_assistant(
    user_id: UUID, content: str, metadata: Dict[str, Any]
) -> None:
```
- Responsible for formatting messages (`QueueMessage`) and sending them to the assistant's input Redis queue (`input_queue`).
- Called by `message_text.py` handler after user and secretary checks pass.

### 3.10 Keyboard Factory (`keyboards/secretary_selection.py`)
```python
def create_secretary_selection_keyboard(secretaries: List[AssistantRead]) -> Keyboard:
```
- Generates the inline keyboard structure for selecting a secretary.
- Takes a list of secretaries and returns a nested list suitable for `TelegramClient.send_message_with_inline_keyboard`.
- Called by `command_start.py` and `message_text.py` handlers.

## 4. Configuration

### 4.1 Settings
```python
class Settings(BaseSettings):
    # Telegram settings
    telegram_token: str
    telegram_rate_limit: int = 30

    # Redis settings
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    input_queue: str = "queue:to_secretary"
    assistant_output_queue: str = "queue:to_telegram"
```

### 4.2 Environment Variables
- `TELEGRAM_TOKEN`: Bot token
- `REDIS_*`: Redis connection settings
- `REST_SERVICE_URL`: REST API endpoint
- `TESTING`: Test mode flag

## 5. Message Processing

### 5.1 Message Flow

The processing flow for incoming updates (messages or callbacks) is as follows:

1.  **Polling (`bot/polling.py`):** Fetches updates from the Telegram API via long polling.
2.  **Dispatching (`bot/dispatcher.py`):** 
    - Receives each update from the polling task.
    - Determines the update type (message, callback query) and identifies the appropriate handler module from `handlers/` (e.g., `command_start`, `message_text`, `command_select_secretary`).
    - Calls the handler function, passing necessary context (Telegram client, REST client, update details).
3.  **Handling (`handlers/`):
    - **Execution:** The specific handler function (e.g., `handle_start`, `handle_text_message`) executes.
    - **User/Secretary Logic:** Interacts with `services/user_service.py` to get/create users and check/assign secretaries using the `RestClient`.
    - **Keyboard Generation:** Uses `keyboards/secretary_selection.py` (if needed) to create inline keyboards.
    - **Sending to Assistant:** For text messages (if user and secretary are valid), interacts with `services/message_queue.py` to format (`QueueMessage`) and push the message to the input Redis queue (`input_queue`).
    - **User Feedback:** Uses the `TelegramClient` to send messages, prompts, or confirmations back to the user and to answer callback queries.
4.  **Response Processing (Parallel Task - `services/response_processor.py`):**
    - **Listening:** Continuously listens to the output Redis queue (`assistant_output_queue`) for responses from the `assistant_service`.
    - **Parsing:** Validates and parses the incoming `AssistantResponseMessage`.
    - **User Lookup:** Uses `RestClient` to get the user's `telegram_id` based on the `user_id` in the response message.
    - **Delivering Response:** Uses the `TelegramClient` to send the final response or error message from the assistant back to the correct user chat.

### 5.2 Error Handling
- Structured error logging with structlog
- User-friendly error messages
- Retry mechanisms for external services
- Graceful degradation

## 6. Testing

### 6.1 Current Implementation
- Smoke test for basic functionality
- Environment configuration for testing
- Basic service connectivity checks

### 6.2 Test Coverage
- Settings validation
- Redis connection
- Client initialization
- Basic service functionality

## 7. Future Enhancements

### 7.1 Planned Improvements
- Enhanced message formatting
- Inline keyboard support
- Rich media handling
- Advanced monitoring

### 7.2 Testing Roadmap
- Unit tests for components
- Integration tests
- E2E test scenarios
- Mock implementations

## 8. Best Practices

### 8.1 Development Guidelines
- Use type hints
- Follow naming conventions
- Document changes
- Maintain test coverage

### 8.2 Error Handling
- Log all errors with context
- Provide user-friendly messages
- Implement retry mechanisms
- Monitor error rates

### 8.3 Performance
- Use async/await for I/O operations
- Implement rate limiting
- Monitor response times
- Optimize Redis usage
