# REST Service – Detailed Overview

## 1. Overview
- **Purpose:** Provides a RESTful API to manage user data, assistant configurations, and operational data.
- **Functions:**
  - CRUD operations for assistants, tools, and scheduled tasks
  - User management and authentication
  - Calendar integration
  - Task scheduling
  - Assistant-user mapping
- **Tech Stack:** 
  - FastAPI for API endpoints
  - SQLModel/SQLAlchemy for ORM
  - PostgreSQL for data storage
  - Alembic for migrations

## 2. Directory Structure
```
rest_service/
├── src/
│   ├── main.py              # FastAPI application entry point
│   ├── database.py          # Database connection and ORM setup
│   ├── config.py            # Configuration settings
│   ├── models/              # Database models (SQLModel)
│   │   ├── base.py          # Base model with timestamps
│   │   ├── assistant.py     # Assistant and tool models
│   │   ├── calendar.py      # Calendar integration models
│   │   ├── cron.py          # Task scheduling models (renamed from reminder.py? Check actual)
│   │   ├── reminder.py      # Reminder models (if exists)
│   │   ├── user.py          # User models
│   │   └── user_secretary.py # User-secretary mapping
│   ├── routers/             # API endpoints
│   │   ├── assistants.py    # Assistant management
│   │   ├── tools.py         # Tool management
│   │   ├── users.py         # User management
│   │   ├── calendar.py      # Calendar integration
│   │   ├── reminders.py     # Reminder scheduling (if exists)
│   │   └── secretaries.py   # Secretary management
│   └── crud/                # CRUD database operations
└── tests/                   # Test suite
```

## 3. Database Models

*(Note: API Schemas (Pydantic models) used for request/response validation are now defined in the `shared_models` package.)*

### 3.1 Base Model
```python
class BaseModel(SQLModel):
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)
```

### 3.2 Assistant Models
*(Enum `AssistantType` is defined in `shared_models.enums`)*
```python
class Assistant(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    is_secretary: bool
    model: str
    instructions: str
    assistant_type: str # Changed from AssistantType enum reference
```

### 3.3 Tool Models
*(Enum `ToolType` is defined in `shared_models.enums`)*
```python
class Tool(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    tool_type: str # Changed from ToolType enum reference
    description: str
    input_schema: Optional[str] = None # Changed from dict to Optional[str]
```

### 3.4 User Models
```python
class TelegramUser(BaseModel, table=True):
    id: int = Field(primary_key=True)
    telegram_id: int = Field(unique=True)
    username: Optional[str]

    # Relationships (Example, adjust based on actual model)
    # reminders: List["Reminder"] = Relationship(back_populates="user")
    # calendar_credentials: Optional["CalendarCredentials"] = Relationship(back_populates="user")
    # secretary_links: List["UserSecretaryLink"] = Relationship(back_populates="user")
```

### 3.5 Calendar Models
```python
class CalendarCredentials(SQLModel, table=True):
    id: int = Field(primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id")
    access_token: str
    refresh_token: str
    token_expiry: datetime
```

### 3.6 Reminder Models (If applicable)
*(Enums `ReminderType`, `ReminderStatus` are defined in `shared_models.enums`)*
```python
class Reminder(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id", index=True)
    assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    created_by_assistant_id: UUID = Field(foreign_key="assistant.id", index=True)
    type: str # Changed from ReminderType
    trigger_at: Optional[datetime] = Field(default=None, index=True)
    cron_expression: Optional[str] = Field(default=None)
    payload: str
    status: str # Changed from ReminderStatus
    last_triggered_at: Optional[datetime] = Field(default=None)
```

### 3.7 User-Secretary Mapping
```python
class UserSecretaryLink(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id")
    secretary_id: UUID = Field(foreign_key="assistant.id")
    is_active: bool
```

## 4. API Endpoints

### 4.1 Assistant Management
- **GET /api/assistants**: List all assistants
- **POST /api/assistants**: Create new assistant
- **GET /api/assistants/{id}**: Get assistant details
- **PUT /api/assistants/{id}**: Update assistant
- **DELETE /api/assistants/{id}**: Delete assistant

### 4.2 Tool Management
- **GET /api/tools**: List all tools
- **POST /api/tools**: Create new tool
- **GET /api/tools/{id}**: Get tool details
- **PUT /api/tools/{id}**: Update tool
- **DELETE /api/tools/{id}**: Delete tool

### 4.3 User Management
- **GET /api/users**: List all users
- **POST /api/users**: Create new user
- **GET /api/users/{id}**: Get user details
- **PUT /api/users/{id}**: Update user
- **DELETE /api/users/{id}**: Delete user

### 4.4 Calendar Integration
- **GET /api/calendar/{user_id}**: Get calendar credentials
- **POST /api/calendar/{user_id}**: Store calendar credentials
- **DELETE /api/calendar/{user_id}**: Remove calendar credentials

### 4.5 Task Scheduling
- **GET /api/cron-jobs**: List all scheduled tasks
- **POST /api/cron-jobs**: Create new task
- **GET /api/cron-jobs/{id}**: Get task details
- **PUT /api/cron-jobs/{id}**: Update task
- **DELETE /api/cron-jobs/{id}**: Delete task

## 5. Configuration

### 5.1 Settings
```python
class Settings(BaseSettings):
    ASYNC_DATABASE_URL: str
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
```

### 5.2 Environment Variables
- `ASYNC_DATABASE_URL`: Database connection string
- `DB_ECHO`: SQL query logging
- `DB_POOL_SIZE`: Connection pool size
- `DB_MAX_OVERFLOW`: Maximum overflow connections

## 6. Database Management

### 6.1 Connection Setup
```python
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)
```

### 6.2 Session Management
```python
AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
```

## 7. Testing

### 7.1 Test Structure
- **Unit Tests:**
  - Model validation
  - API endpoints
  - Database operations

### 7.2 Test Environment
- Isolated test database
- Mock services
- Environment variables
- Test fixtures

## 8. Best Practices

### 8.1 Development Guidelines
- Use type hints
- Follow naming conventions
- Document changes
- Maintain test coverage

### 8.2 Error Handling
- Structured logging
- Validation errors
- Database errors
- API errors

### 8.3 Performance
- Connection pooling
- Query optimization
- Caching
- Indexing
