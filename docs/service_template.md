# Service Template

## Directory Structure

```
name_service/
├── src/                    # Source code
│   ├── api/               # API endpoints and routers
│   │   ├── endpoints/     # API endpoint handlers
│   │   │   ├── __init__.py
│   │   │   └── resource_endpoints.py
│   │   ├── __init__.py
│   │   └── router.py
│   ├── core/              # Core business logic
│   │   ├── __init__.py
│   │   └── service.py
│   ├── models/            # Data models and schemas
│   │   ├── __init__.py
│   │   └── resource.py
│   ├── services/          # External service integrations
│   │   ├── __init__.py
│   │   └── external_service.py
│   ├── utils/             # Utility functions
│   │   ├── __init__.py
│   │   └── helpers.py
│   ├── __init__.py
│   └── main.py            # Application entry point
├── tests/                 # Test files
│   ├── api/              # API tests
│   │   ├── __init__.py
│   │   └── test_endpoints.py
│   ├── core/             # Core logic tests
│   │   ├── __init__.py
│   │   └── test_service.py
│   ├── conftest.py       # Pytest fixtures
│   └── __init__.py
├── alembic/              # Database migrations
│   ├── versions/        # Migration files
│   ├── env.py
│   └── alembic.ini
├── docs/                # Service documentation
│   ├── api.md          # API documentation
│   └── architecture.md # Architecture documentation
├── .context/           # LLM context files
│   ├── service.context.md    # Service-specific context
│   ├── api.context.md       # API-specific context
│   ├── models.context.md    # Models-specific context
│   └── services.context.md  # External services context
├── .env.example        # Example environment variables
├── .gitignore         # Git ignore rules
├── Dockerfile         # Production Dockerfile
├── Dockerfile.test    # Test environment Dockerfile
├── docker-compose.test.yml  # Test environment compose file
└── pyproject.toml     # Project configuration and dependencies
```

## File Templates

### 1. Main Application Entry Point (src/main.py)
```python
from fastapi import FastAPI
from src.api.router import router
from src.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION
)

app.include_router(router, prefix=settings.API_PREFIX)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2. Configuration (src/core/config.py)
```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str
    VERSION: str
    DESCRIPTION: str
    API_PREFIX: str
    # Add other settings

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### 3. API Router (src/api/router.py)
```python
from fastapi import APIRouter
from src.api.endpoints import resource_endpoints

router = APIRouter()

router.include_router(
    resource_endpoints.router,
    prefix="/resources",
    tags=["resources"]
)
```

### 4. Endpoint Handler (src/api/endpoints/resource_endpoints.py)
```python
from fastapi import APIRouter, Depends
from src.core.service import Service
from src.models.resource import ResourceCreate, ResourceResponse

router = APIRouter()

@router.post("/", response_model=ResourceResponse)
async def create_resource(
    resource: ResourceCreate,
    service: Service = Depends()
):
    return await service.create_resource(resource)
```

### 5. Service Layer (src/core/service.py)
```python
from src.models.resource import ResourceCreate, ResourceResponse
from src.services.external_service import ExternalService

class Service:
    def __init__(self, external_service: ExternalService):
        self.external_service = external_service

    async def create_resource(self, resource: ResourceCreate) -> ResourceResponse:
        # Implement business logic
        pass
```

### 6. Models (src/models/resource.py)
```python
from pydantic import BaseModel
from datetime import datetime

class ResourceBase(BaseModel):
    name: str
    description: str | None = None

class ResourceCreate(ResourceBase):
    pass

class ResourceResponse(ResourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

### 7. External Service (src/services/external_service.py)
```python
from typing import Any
import httpx

class ExternalService:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        # Implement external service communication
        pass
```

### 8. Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /src

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY . .

# Run the application
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9. docker-compose.test.yml
```yaml
version: '3.8'

services:
  test:
    build:
      context: .
      dockerfile: Dockerfile.test
    environment:
      - TESTING=1
      - PYTHONPATH=/src
```

### 10. pyproject.toml
```toml
[tool.poetry]
name = "smart-assistant-service"
version = "0.1.0"
description = "Smart Assistant Service Template"
authors = ["Your Name <your.email@example.com>"]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = "^0.24.0"
pydantic = "^2.4.2"
pydantic-settings = "^2.0.3"
httpx = "^0.25.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.3"
pytest-asyncio = "^0.21.1"
pytest-cov = "^4.1.0"
black = "^23.10.1"
isort = "^5.12.0"
flake8 = "^6.1.0"
mypy = "^1.6.1"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

## Additional Guidelines

### 1. Testing
- Use pytest for testing
- Write unit tests for all business logic
- Write integration tests for API endpoints
- Use pytest-cov for coverage reporting
- Use pytest-asyncio for async tests

### 2. Code Quality
- Use black for code formatting
- Use isort for import sorting
- Use flake8 for linting
- Use mypy for type checking
- Follow PEP 8 guidelines

### 3. Documentation
- Document all public APIs
- Include docstrings for all functions and classes
- Keep README.md up to date
- Document environment variables
- Include API documentation

### 4. Error Handling
- Use custom exception classes
- Implement proper error responses
- Log errors appropriately
- Include error details in responses

### 5. Security
- Validate all input data
- Use proper authentication and authorization
- Keep dependencies updated
- Follow security best practices

## Context Files

### 1. Service Context (.context/service.context.md)
```markdown
# Service Context

## Overview
- Service name and purpose
- Main responsibilities
- Key features
- Dependencies on other services

## Architecture
- High-level architecture
- Key components
- Data flow
- Integration points

## Configuration
- Required environment variables
- Configuration options
- Default values
- Configuration validation

## Development
- Setup instructions
- Development workflow
- Testing strategy
- Deployment process

## Maintenance
- Monitoring
- Logging
- Backup procedures
- Update procedures
```

### 2. API Context (.context/api.context.md)
```markdown
# API Context

## Endpoints
- List of all endpoints
- Request/response formats
- Authentication requirements
- Rate limiting

## Data Models
- Request models
- Response models
- Validation rules
- Example payloads

## Error Handling
- Error codes
- Error responses
- Retry policies
- Error logging

## Security
- Authentication methods
- Authorization rules
- Input validation
- Security headers
```

### 3. Models Context (.context/models.context.md)
```markdown
# Models Context

## Database Models
- Table structures
- Relationships
- Indexes
- Constraints

## Pydantic Models
- Schema definitions
- Validation rules
- Serialization options
- Example usage

## Data Types
- Custom types
- Type conversions
- Default values
- Null handling
```

### 4. Services Context (.context/services.context.md)
```markdown
# External Services Context

## Service Integrations
- List of external services
- Integration methods
- Authentication
- Rate limits

## API Clients
- Client implementations
- Error handling
- Retry logic
- Timeout settings

## Data Flow
- Request flow
- Response handling
- Error propagation
- Logging
```

### Guidelines for Context Files

1. **Content Organization**
   - Use clear hierarchical structure
   - Include code examples where relevant
   - Keep information up to date
   - Link to related documentation

2. **Maintenance**
   - Update when adding new features
   - Review during code reviews
   - Keep examples current
   - Remove outdated information

3. **Format**
   - Use Markdown for formatting
   - Include code blocks with language specification
   - Use tables for structured data
   - Include diagrams when helpful

4. **Best Practices**
   - Keep files focused and concise
   - Use consistent terminology
   - Include troubleshooting guides
   - Document known issues 