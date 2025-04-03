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
├── src/                    # Source code
│   ├── client/            # External service clients
│   │   ├── telegram.py    # Telegram Bot API client
│   │   └── rest.py        # REST API client
│   ├── handlers/          # Message and command handlers
│   │   └── start.py       # /start command handler
│   ├── services/          # Service logic
│   │   └── response_handler.py  # Assistant response handling
│   ├── config/            # Configuration
│   │   └── settings.py    # Service settings
│   ├── utils/             # Utilities
│   └── main.py            # Service entry point
├── tests/                 # Test suite
│   ├── test_smoke.py     # Basic functionality tests
│   └── .env.test         # Test environment configuration
└── Dockerfile            # Container configuration
```

## 3. Key Components

### 3.1 Telegram Client
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

### 3.2 REST Client
```python
class RestClient:
    def __init__(self):
        self.base_url = settings.rest_service_url
        self.api_prefix = "/api"
```

- Manages communication with REST API service
- Handles user management operations
- Implements get_or_create_user functionality
- Includes error handling and logging

### 3.3 Response Handler
```python
async def handle_assistant_responses(telegram: TelegramClient, redis: aioredis.Redis):
    """Handle responses from assistant service."""
```

- Processes responses from assistant service
- Manages Redis queue for responses
- Handles error cases and user notifications
- Implements retry mechanisms

### 3.4 Command Handlers
```python
async def handle_start(telegram: TelegramClient, rest: RestClient, chat_id: int, user: Dict[str, Any]):
    """Handle /start command."""
```

- Processes /start command
- Manages user registration
- Sends appropriate welcome messages
- Handles error cases

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
1. Receive message from Telegram
2. Identify user via REST API
3. Process command or forward to assistant
4. Handle assistant response
5. Send response back to user

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
