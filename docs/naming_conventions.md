# Naming Conventions in Smart Assistant Project

## 1. General Principles

### 1.1. Naming Styles
- **snake_case**: for Python files, directories, variables, and functions
- **kebab-case**: for Docker container names
- **PascalCase**: for Python classes
- **UPPER_SNAKE_CASE**: for constants and environment variables

### 1.2. Prefixes
- All services and their components must have the `name_service` format
- All containers must have the `name-service` format
- All Docker images must have the `name_service` format

## 2. Service Naming

### 2.1. Service Directories
```
assistant_service/      # Assistant service
rest_service/          # REST API service
calendar_service/      # Calendar service
cron_service/          # Scheduler service
bot_service/           # Telegram bot
```

### 2.2. Containers in docker-compose.yml
```yaml
services:
  assistant_service:
    container_name: assistant-service
  rest_service:
    container_name: rest-service
  calendar_service:
    container_name: calendar-service
  cron_service:
    container_name: cron-service
  bot_service:
    container_name: bot-service
```

### 2.3. Docker Images
```yaml
services:
  assistant_service:
    image: assistant_service:latest
  rest_service:
    image: rest_service:latest
  calendar_service:
    image: calendar_service:latest
  cron_service:
    image: cron_service:latest
  bot_service:
    image: bot_service:latest
```

## 3. Code Naming

### 3.1. Python Files and Directories
- All files and directories in snake_case
- Test files must end with `_test.py`
- Configuration files must end with `_config.py`
- Examples:
  ```
  src/
  ├── api/
  │   ├── endpoints/
  │   │   ├── user_endpoints.py
  │   │   └── user_endpoints_test.py
  │   └── router.py
  ├── core/
  │   ├── config.py
  │   └── config_test.py
  └── utils/
      ├── helpers.py
      └── helpers_test.py
  ```

### 3.2. Classes
- Use PascalCase
- Names should be nouns
- Examples:
  ```python
  class UserService:
  class DatabaseConfig:
  class TelegramBot:
  ```

### 3.3. Functions and Variables
- Use snake_case
- Function names should be verbs
- Variable names should be nouns
- Examples:
  ```python
  def get_user_by_id():
  def process_message():
  user_count = 0
  message_text = ""
  ```

### 3.4. Constants
- Use UPPER_SNAKE_CASE
- Examples:
  ```python
  MAX_RETRY_COUNT = 3
  DEFAULT_TIMEOUT = 30
  API_VERSION = "v1"
  ```

## 4. Database Naming

### 4.1. Tables
- Use snake_case
- `sa_` prefix for all tables
- Examples:
  ```
  sa_users
  sa_messages
  sa_configurations
  ```

### 4.2. Columns
- Use snake_case
- Examples:
  ```sql
  user_id
  created_at
  updated_at
  is_active
  ```

## 5. Environment Variables Naming

### 5.1. General Rules
- Use UPPER_SNAKE_CASE
- `SA_` prefix for all variables
- Group by services
- Examples:
  ```
  SA_REST_HOST=localhost
  SA_REST_PORT=8000
  SA_BOT_TOKEN=123456
  SA_CALENDAR_API_KEY=abcdef
  ```

### 5.2. Service Grouping
```
# REST Service
SA_REST_HOST=
SA_REST_PORT=
SA_REST_DB_URL=

# Bot Service
SA_BOT_TOKEN=
SA_BOT_WEBHOOK_URL=

# Calendar Service
SA_CALENDAR_API_KEY=
SA_CALENDAR_CLIENT_ID=

# Assistant Service
SA_ASSISTANT_API_KEY=
SA_ASSISTANT_MODEL=
```

## 6. Documentation Naming

### 6.1. Documentation Files
- Use snake_case
- `docs_` prefix for technical documentation
- Examples:
  ```
  docs_architecture.md
  docs_api.md
  docs_deployment.md
  ```

### 6.2. Documentation Sections
- Use PascalCase for headers
- Use snake_case for links
- Examples:
  ```markdown
  # System Architecture
  # API Endpoints
  # Deployment Process
  ```

## 7. Exceptions

### 7.1. Allowed Exceptions
- PyPI package names (must be unique)
- Third-party configuration file names
- Database migration names (must be unique)

### 7.2. Exception Requirements
- Document all exceptions
- Explain the reason for the exception
- Provide alternatives if available 