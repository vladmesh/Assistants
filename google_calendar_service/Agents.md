# Google Calendar Service Detailed Overview

## 1. Overview
- **Purpose:** Integrates with Google Calendar API for event management.
- **Functions:** 
  - OAuth 2.0 authorization and token management
  - Event retrieval and creation
  - Integration with REST API for user data
  - Redis-based message queuing
- **Tech Stack:** 
  - FastAPI for asynchronous processing
  - Google Calendar API integration
  - Redis for message queuing
  - Dockerized microservice architecture

## 2. Directory Structure
```
google_calendar_service/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── api/                 # API endpoints
│   │   └── routes.py        # API routes and handlers
│   ├── services/            # Business logic
│   │   ├── calendar.py      # Google Calendar service
│   │   ├── redis_service.py # Redis integration
│   │   └── rest_service.py  # REST API integration
│   ├── config/             # Configuration
│   │   └── settings.py     # Application settings
│   └── schemas/            # Pydantic models
│       └── calendar.py     # Calendar data models
└── tests/                  # Test suite
    ├── conftest.py         # Test fixtures
    ├── test_routes.py      # API endpoint tests
    └── .env.test           # Test environment config
```

## 3. Key Components

### 3.1 FastAPI Application
- Initializes middleware and CORS
- Manages service lifecycle
- Handles startup/shutdown events
- Provides health check endpoint

### 3.2 GoogleCalendarService
- **OAuth Management:**
  - `get_auth_url(state)`: Generates OAuth URL
  - `handle_callback(code)`: Processes OAuth callback
  - `_refresh_credentials_if_needed()`: Token refresh logic

- **Calendar Operations:**
  - `get_events()`: Retrieves calendar events
  - `create_event()`: Creates new events
  - `_refresh_credentials_if_needed()`: Token management

### 3.3 RedisService
- Manages message queues
- Handles notifications
- Implements retry mechanisms
- Provides connection pooling

### 3.4 RestService
- User data management
- Token storage
- Configuration retrieval
- Error handling and retries

## 4. API Endpoints

### 4.1 Authentication
- **GET `/auth/url/{user_id}`**
  - Returns OAuth URL for user authorization
  - Validates user existence
  - Checks for existing credentials

- **POST `/auth/callback`**
  - Processes OAuth callback
  - Exchanges code for tokens
  - Stores credentials in REST service

### 4.2 Events
- **GET `/events/{user_id}`**
  - Retrieves user's calendar events
  - Supports time range filtering
  - Handles token refresh

- **POST `/events/{user_id}`**
  - Creates new calendar events
  - Validates event data
  - Handles timezone conversion

## 5. Data Models

### 5.1 Event Models
```python
class EventBase(BaseModel):
    summary: str
    description: Optional[str]
    location: Optional[str]

class EventCreate(EventBase):
    start: Dict[str, str]
    end: Dict[str, str]

class EventResponse(EventBase):
    id: str
    start: Dict[str, str]
    end: Dict[str, str]
    htmlLink: Optional[str]
    status: str
```

## 6. Configuration

### 6.1 Settings
```python
class Settings(BaseSettings):
    # Google OAuth settings
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str
    GOOGLE_TOKEN_URI: str = "https://oauth2.googleapis.com/token"
    
    # Redis settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    # REST service settings
    REST_SERVICE_URL: str = "http://rest_service:8000"
```

## 7. Testing

### 7.1 Test Structure
- **Unit Tests:**
  - Service functionality
  - Model validation
  - Error handling

- **Integration Tests:**
  - API endpoints
  - Service interactions
  - Redis operations

### 7.2 Test Environment
- Isolated test database
- Mock services
- Environment variables
- Test fixtures

## 8. Integration & Security

### 8.1 Inter-Service Communication
- **REST API:**
  - User data management
  - Token storage
  - Configuration retrieval

- **Redis:**
  - Message queuing
  - Notifications
  - Event updates

### 8.2 Security Measures
- OAuth 2.0 implementation
- Token validation
- Credential refresh
- Input sanitization

## 9. Best Practices

### 9.1 Development Guidelines
- Use type hints
- Follow naming conventions
- Document changes
- Maintain test coverage

### 9.2 Error Handling
- Structured logging
- Retry mechanisms
- Graceful degradation
- User-friendly messages

### 9.3 Performance
- Async/await for I/O
- Connection pooling
- Token caching
- Rate limiting

