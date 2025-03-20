# High-Level Overview

## Services

The project is divided into several independent microservices:
- **assistant**  
  - Core engine for handling user messages and coordinating various LLM-based functionalities.
  - Manages context, threads, and asynchronous message processing via Redis.
  
- **rest_service**  
  - Provides a REST API for managing user data, assistant configurations, and related models.
  - Handles CRUD operations for assistants, tools, and scheduled tasks.
  - Uses PostgreSQL for data storage and Alembic for database migrations.
  
- **google_calendar_service**  
  - Integrates with Google Calendar for event management.
  - Implements OAuth 2.0 authorization, token management, and calendar event retrieval/creation.
  
- **cron_service**  
  - A scheduler service using APScheduler to manage and execute scheduled tasks.
  - Periodically pulls job configurations from the REST API and sends notifications via Redis.
  
- **tg_bot**  
  - A Telegram Bot interface for end-user interaction.
  - Receives user messages, identifies users via REST API, and sends formatted responses.

## Deployment

- **Docker & Docker Compose**  
  - Each service runs in its own container.
  - Deployment is managed using `docker compose` commands.
  - Example for running tests and managing containers:
    - **Build and start containers:**  
      ```bash
      docker compose up --build -d
      ```
    - **Check container status:**  
      ```bash
      docker compose ps
      ```

- **Environment Variables**  
  - Configuration (e.g., database URLs, tokens) is managed via environment variables.
  - For testing, a separate Docker Compose file (`docker-compose.test.yml`) is used to set up an isolated test environment.

## Testing

- **Types of Tests:**
  - **Unit Tests:**  
    - Validate individual components, business logic, and data models.
    - Use mocks for external dependencies.
  - **Integration Tests:**  
    - Verify API endpoints and inter-service interactions.
    - Ensure correct behavior of asynchronous operations.
  - **End-to-End Tests:**  
    - Test full user workflows in a complete Docker environment.
    - Enforce isolation from the local development environment.

- **Test Execution:**
  - Tests are designed to run exclusively within Docker containers.
  - A dedicated script (`run_tests.sh`) is provided to launch all tests:
    ```bash
    ./manage.py test --service rest_service
    ```
  - Direct execution inside a container (e.g., `docker compose exec rest_service python -m pytest`) is discouraged.

## Scripts & Tools

### Management Scripts (manage.py)
- **migrate:**  
  - Create and apply database migrations.
  - Example:  
    ```bash
    ./manage.py migrate "Initial migration"
    ```
- **upgrade:**  
  - Apply pending migrations.
- **test:**  
  - Run the full suite of tests in the appropriate Docker container.
- **rebuild:**  
  - Rebuild specific service containers.  
    Example:  
    ```bash
    ./manage.py rebuild --service rest_service
    ```
- **restart:**  
  - Restart the services.
- **start/stop:**  
  - Manage service lifecycle.

### Tools for the Assistant

- **Calendar Tool:**  
  - Handles creation and retrieval of calendar events.
  - Integrates with Google Calendar API.
  
- **Reminder Tool:**  
  - Manages user reminders and notifications.
  
- **Time Tool:**  
  - Provides time-related functionalities.
  
- **Sub Assistant Tool:**  
  - Delegates specialized tasks to sub-assistants.
  
- **Weather Tool:**  
  - Fetches and provides weather information (if integrated).

---

This high-level summary encapsulates the primary components, deployment strategy, testing approach, and management scripts/tools of the Smart Assistant project.

# General Recommendations and Future Plans

## Best Practices & Internal Guidelines
- **Minimal Changes:** Modify only what’s necessary and avoid optimizations without validation.
- **Strict Verification:** Run tests for every change; verify service status and logs after deployments.
- **Clear Communication:** Use English for code comments, commit messages, and documentation.
- **Docker-First Approach:** Always manage containers using `docker compose` and check service status (e.g., using `docker compose ps`).
- **Database Integrity:** Use synchronous migrations (psycopg2) for Alembic and log connection URLs for debugging.

## Planned Enhancements
- **Caching:** Implement Redis-based caching to speed up data retrieval.
- **Dynamic Configuration:** Develop a mechanism for real-time configuration updates across services.
- **Expanded LLM Integrations:** Integrate additional LLM APIs beyond OpenAI.
- **Enhanced Testing:** Introduce more comprehensive end-to-end and performance tests, ensuring all tests run only within Docker.
- **CI/CD Automation:** Automate Docker image builds, test executions, and deployments in the CI/CD pipeline.
- **Improved Documentation:** Continuously update internal guides and documentation as features evolve.

## Future Roadmap
- **Centralized Logging & Monitoring:** Integrate systems like ELK Stack, Prometheus, Grafana, and OpenTelemetry for better observability.
- **Workflow Automation:** Explore integration with workflow tools (e.g., n8n) for advanced process automation.
- **Code Refactoring:** Incrementally refactor code to improve modularity and performance without disrupting current functionality.


detailed information on each service in the "llm_context_**" files