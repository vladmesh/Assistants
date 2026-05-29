# Smart Assistant Admin Panel

## Overview
The admin panel is a Streamlit web interface for managing every aspect of Smart Assistant. It provides convenient access to managing users, assistants, tools, and system settings.

## Main Sections

### 1. User Management
- View the list of all users
- Filter and search users
- Detailed user information:
  - Core data (ID, Telegram ID, username)
  - Interaction history
  - Assigned assistants
  - Usage statistics
- Ability to block/unblock users
- Access-rights management

### 2. Assistant Management
- Create new assistants
- Edit existing assistants:
  - Name and description
  - OpenAI model
  - Instructions
  - Assistant type
  - Active status
- Assign tools to assistants
- View usage statistics
- Test assistants in real time

### 3. Tool Management
- Create new tools
- Edit existing tools:
  - Name and description
  - Input schema
  - Tool type
  - Active status
- Assign tools to assistants
- Test tools

### 4. System Monitoring
- Usage statistics:
  - Number of active users
  - Number of messages
  - Response time
  - Resource usage
- System logs
- Status of all services
- Errors and warnings

### 5. System Settings
- OpenAI configuration:
  - API keys
  - Models
  - Limits
- Redis settings
- Database settings
- General system settings

### 6. Global System Settings
- Manage shared assistant behavior parameters:
  - **Summarization prompt:** Edit the prompt used to summarize dialog history.
  - **Context window size:** Set the maximum number of tokens passed to the LLM.

### 7. Task Management
- View scheduled tasks
- Create new tasks
- Edit existing tasks
- Monitor task execution
- Execution history

## Technical Requirements

### Security
- Administrator authentication
- Access-rights segregation
- Logging of administrator actions
- Protection against CSRF and XSS attacks

### Performance
- Data caching
- Pagination for large lists
- Asynchronous data loading
- Database query optimization

### Interface
- Responsive design
- Dark/light theme
- Intuitive navigation
- Informative error messages
- Confirmation of important actions

## Integration
- REST API for all operations
- WebSocket for real-time updates
- Integration with the logging system
- Data export to various formats

## Additional Features
- Data backup
- Restore from backup
- Configuration export/import
- Bulk data operations
- Notification system for administrators

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
