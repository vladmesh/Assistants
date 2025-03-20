# REST Service – Detailed Overview

## 1. Overview
- **Purpose:** Provides a RESTful API to manage user data, assistant configurations, and operational data.
- **Functions:**
  - CRUD operations for assistants, tools, links, and scheduled tasks.
  - Data validation using Pydantic models.
  - Persistent storage with PostgreSQL.

## 2. Directory Structure (Simplified)
rest_service/
├── app/                  
│   ├── models/          
│   │   ├── assistant.py   # Assistant and tool models
│   │   ├── base.py        # Base models
│   │   ├── calendar.py    # Calendar-related models
│   │   ├── cron.py        # Scheduler models
│   │   └── user.py        # User models
│   ├── routers/         
│   │   ├── assistants.py      # Assistant management endpoints
│   │   ├── assistant_tools.py # Linking assistants and tools
│   │   ├── calendar.py        # Calendar management endpoints
│   │   ├── cron_jobs.py       # Task scheduling endpoints
│   │   ├── tools.py           # Tool management endpoints
│   │   └── users.py           # User management endpoints
│   ├── database.py        # Database connection and ORM setup
│   ├── main.py            # Application entry point
│   └── config.py          # Configuration settings
├── tests/                 # Automated tests
└── requirements.txt       # Project dependencies

## 3. Key Components

- **FastAPI Application (main.py):**
  - Initializes the REST API, attaches routers, and manages the service lifecycle.

- **Database Module (database.py):**
  - Sets up the PostgreSQL connection using SQLAlchemy/SQLModel.
  - Manages connection pooling, session handling, and Alembic migrations.

- **Routers:**
  - Organize endpoints for assistants, tools, calendar, cron jobs, and users.
  - Validate incoming data with Pydantic and interface with ORM models.

- **Configuration (config.py):**
  - Centralizes environment variables and service settings for consistent behavior.

- **Testing Framework:**
  - Contains unit and integration tests to verify endpoints and database operations.

## 4. Integration & Workflow

- **Inter-Service Communication:**
  - Acts as the central hub by providing REST endpoints for other microservices (assistant, google_calendar_service, cron_service, tg_bot).
  - Exposes APIs to manage user data, configuration, and operational state.

- **Request Handling:**
  - Validates incoming requests using Pydantic models.
  - Processes CRUD operations by interfacing with the PostgreSQL database through SQLAlchemy/SQLModel.

- **Data Consistency & Migrations:**
  - Ensures data integrity via ORM-based models and structured validations.
  - Manages database schema changes with Alembic migrations.

- **Configuration Management:**
  - Centralized settings in `config.py` control service behavior and environment-specific configurations.


## 6. Models & Relationships

- **Assistant Model:**
  - **Fields:**  
    - `id` (UUID)
    - `name`
    - `is_secretary`
    - `model`
    - `instructions`
    - `assistant_type` (e.g., "llm" or "openai_api")
    - `openai_assistant_id`
    - `is_active`
    - `created_at`, `updated_at`
  - **Relationships:**  
    - Associated with multiple tools via `AssistantToolLink`.
    - Engaged in conversation threads managed by `UserAssistantThread`.

- **Tool Model:**
  - **Fields:**  
    - `id` (UUID)
    - `name`
    - `tool_type` (e.g., "calendar", "reminder", "time", "weather", "sub_assistant")
    - `description`
    - `input_schema` (JSON schema)
    - `assistant_id` (optional, for sub_assistant type)
    - `is_active`
    - `created_at`, `updated_at`
  - **Relationships:**  
    - Linked to an assistant, or utilized within sub-assistant contexts.

- **AssistantToolLink Model:**
  - **Purpose:** Establishes a many-to-many relationship between assistants and tools.
  - **Key Fields:**  
    - `sub_assistant_id`
    - `is_active`
    - `created_at`, `updated_at`

- **UserAssistantThread Model:**
  - **Purpose:** Stores conversation thread identifiers for each user-assistant pair.
  - **Details:**  
    - Ensures a unique mapping between `user_id` and `assistant_id` to maintain conversation continuity.

- **TelegramUser Model:**
  - **Fields:**  
    - `id` (Integer, Primary Key)
    - `telegram_id` (BigInteger, Unique)
    - `username` (Optional String)
    - `created_at`, `updated_at` (from BaseModel)
  - **Relationships:**  
    - Associated with multiple `CronJob`s
    - Has one `CalendarCredentials`

- **CalendarCredentials Model:**
  - **Fields:**  
    - `id` (Integer, Primary Key)
    - `user_id` (Foreign Key to TelegramUser)
    - `access_token` (String)
    - `refresh_token` (String)
    - `token_expiry` (DateTime)
    - `created_at`, `updated_at` (DateTime)
  - **Relationships:**  
    - Belongs to one `TelegramUser`

- **CronJob Model:**
  - **Fields:**  
    - `id` (Integer, Primary Key)
    - `name` (String)
    - `type` (CronJobType Enum: "notification" or "schedule")
    - `cron_expression` (String)
    - `user_id` (Foreign Key to TelegramUser)
    - `created_at`, `updated_at` (from BaseModel)
  - **Relationships:**  
    - Belongs to one `TelegramUser`
    - Has many `CronJobNotification`s
    - Has many `CronJobRecord`s

- **CronJobNotification Model:**
  - **Fields:**  
    - `id` (Integer, Primary Key)
    - `cron_job_id` (Foreign Key to CronJob)
    - `message` (String)
    - `created_at`, `updated_at` (from BaseModel)

- **CronJobRecord Model:**
  - **Fields:**  
    - `id` (Integer, Primary Key)
    - `cron_job_id` (Foreign Key to CronJob)
    - `started_at` (DateTime)
    - `finished_at` (Optional DateTime)
    - `status` (CronJobStatus Enum: "created", "running", "done", "failed")
    - `created_at`, `updated_at` (from BaseModel)

- **BaseModel:**
  - **Purpose:** Base class for all models providing common functionality
  - **Fields:**  
    - `created_at` (DateTime, UTC)
    - `updated_at` (DateTime, UTC)
  - **Features:**  
    - Automatic timestamp management
    - UTC timezone handling
    - Automatic update of `updated_at` on model changes
