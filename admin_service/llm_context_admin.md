# Admin Service

## Overview

Admin Service is a microservice that provides an administrative interface for managing Smart Assistant. The service is built on Streamlit and provides a convenient web interface for system administrators.

## Architecture

The service consists of the following components:

- **Streamlit UI**: Web interface for interaction with administrators
- **REST Client**: Client for interaction with REST API
- **Configuration**: Service settings

## Functionality

### Current Functionality

- **User Management**: Display a list of all users in the system

### Planned Functionality

- **User Management**: Create, edit, and delete users
- **Assistant Management**: Create, edit, and delete assistants
- **Tool Management**: Create, edit, and delete tools
- **Task Management**: Create, edit, and delete tasks
- **Statistics**: Display system usage statistics

## Deployment

The service is deployed as a Docker container and is available on port 8501.

```bash
# Start the service
docker compose up -d admin_service

# View logs
docker compose logs -f admin_service
```

## Development

### Project Structure

```
admin_service/
├── src/                    # Source code
│   ├── admin_service/      # Service package
│   ├── config.py           # Configuration
│   ├── main.py             # Entry point
│   └── rest_client.py      # REST API client
├── tests/                  # Tests
├── Dockerfile              # Production Dockerfile
├── Dockerfile.test         # Test Dockerfile
├── docker-compose.test.yml # Test configuration
└── pyproject.toml          # Poetry dependencies and settings
```

### Running Tests

```bash
# Run tests
docker compose -f admin_service/docker-compose.test.yml up --build
```

## Interaction with Other Services

### REST Service

Admin Service interacts with the REST Service to obtain data about users, assistants, tools, and tasks.

## Configuration

The service uses the following environment variables:

- `REST_SERVICE_URL`: REST API URL (default: http://rest_service:8000)
- `LOG_LEVEL`: Logging level (default: INFO) 