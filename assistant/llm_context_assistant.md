# Assistant Service Detailed Overview

## 1. Overview
The assistant service is the core engine of the Smart Assistant project. It handles:
- Processing of incoming user messages.
- Management of conversation context.
- Coordination of tool invocations and delegation to sub-assistants.
- Asynchronous message processing via Redis queues.

## 2. Directory Structure

assistant/src/
├── assistants/           # Implementations of various assistant types
│   ├── base.py           # Abstract base class for all assistants
│   ├── factory.py        # Factory for creating main and sub-assistants
│   ├── llm_chat.py       # Base implementation for LLM-based chat assistants
│   ├── openai_assistant.py  # Assistant integrating with the OpenAI API
│   ├── secretary.py      # Primary (Secretary) assistant managing overall interactions
│   └── sub_assistant.py  # Specialized sub-assistants for delegated tasks
├── tools/                # Tools used by assistants to extend functionality
│   ├── base.py           # Base tool class with common functionality
│   ├── calendar_tool.py  # Tool for calendar operations
│   ├── reminder_tool.py  # Tool for managing reminders
│   ├── rest_service_tool.py  # Tool for interfacing with REST services
│   ├── sub_assistant_tool.py # Wrapper to treat sub-assistants as tools
│   └── time_tool.py      # Tool for time-related operations
├── messages/             # Message handling: parsing, formatting, and context enrichment
│   ├── base.py          # Base message class with automatic timestamp and source
│   └── types.py         # Specific message types (Human, Secretary, Tool, System)
├── services/             # Clients for external services and inter-service communication
├── storage/              # Context and message storage (e.g., Redis or database)
├── config/               # Service configuration and environment settings
├── core/                 # Core logic for message processing and orchestration
├── utils/                # Utility functions and helper modules
└── orchestrator.py       # Main orchestrator coordinating message processing, tool execution, and assistant delegation

## 3. Key Components

### Message System
- **Base Message Class:**
  - Automatic timestamp generation in UTC
  - Internal source field with automatic setting
  - Metadata support through additional_kwargs
  - String representation for LLM compatibility
  - Format: `[SOURCE] (TIMESTAMP) CONTENT`

- **Message Types:**
  - `HumanMessage`: User messages (source: HUMAN)
  - `SecretaryMessage`: Secretary responses (source: SECRETARY)
  - `ToolMessage`: Tool responses (source: TOOL)
  - `SystemMessage`: System messages (source: SYSTEM)

- **Message Thread:**
  - Stores conversation history
  - Tracks creation and update timestamps
  - Provides message retrieval and management

### Assistant Orchestrator
- **Role:**  
  - Coordinates incoming messages.
  - Determines which assistant or tool should handle a request.
  - Manages the lifecycle of messages from intake to response.
- **Mechanism:**  
  - Listens to a Redis queue (e.g., `REDIS_QUEUE_TO_SECRETARY`).
  - Dispatches tasks based on message content and context.

### Assistant Factory
- **Purpose:**  
  - Instantiates various types of assistants based on configuration and request context.
- **Types Created:**  
  - Main assistant (SecretaryLLMChat).
  - Sub-assistants (SubAssistantLLMChat) for domain-specific tasks.

### Assistant Implementations
- **BaseAssistant:**  
  - Provides an abstract foundation for common assistant functionality.
- **OpenAIAssistant:**  
  - Integrates with the OpenAI API.
  - Uses thread-based context to maintain conversation state.
- **SecretaryLLMChat:**  
  - Acts as the primary interface for user interactions.
  - Routes requests to appropriate tools or sub-assistants.
- **SubAssistantLLMChat:**  
  - Specialized assistants designed to handle delegated, specific tasks.

### Tools
- **Purpose:**  
  - Extend the capabilities of the assistant by providing domain-specific functions.
- **Key Tools:**
  - **CalendarTool:** Manages calendar events (creation, listing).
  - **ReminderTool:** Handles reminders and notifications.
  - **TimeTool:** Provides time-related operations.
  - **SubAssistantTool:** Enables delegation to sub-assistants.
  - **RestServiceTool:** Interfaces with external REST APIs to fetch or update data.

## 4. Message & Context Handling
- **Input Processing:**  
  - Messages are fetched asynchronously from a Redis queue.
  - Each message automatically gets timestamp and source.
- **Context Management:**  
  - OpenAIAssistant uses thread-based storage.
  - Other LLM assistants leverage Redis-based storage for conversation history.
- **Tool Coordination:**  
  - The orchestrator evaluates the message content to decide which tool(s) to invoke.
  - Ensures the correct context is passed along with each tool call.

## 5. External Communication
- **Service Clients (services/):**  
  - Handle REST API interactions with external services.
  - Facilitate communication between microservices (e.g., with the REST API service, Google Calendar service).
- **Asynchronous Messaging:**  
  - Utilizes Redis for both message intake and response delivery.

## 6. Error Handling & Logging
- **Centralized Error Management:**  
  - Implements structured error handling across components.
  - Logs key operations and exceptions for debugging and monitoring.
- **Retries & Timeouts:**  
  - Incorporates retry mechanisms to handle transient errors and API timeouts.

## 7. Extensibility & Modularity
- **Plug-and-Play Design:**  
  - New assistant types and tools can be integrated with minimal changes.
- **Unified Interfaces:**  
  - All assistants and tools adhere to defined interfaces, ensuring consistency.
- **Configuration Driven:**  
  - Service behavior is controlled via configuration files in the `config/` directory.

## 8. Additional Utilities & Configurations
- **Utility Functions (utils/):**  
  - Provide common functionality used across the service.
- **Core Logic (core/):**  
  - Contains essential routines that integrate various components.
- **Configuration (config/):**  
  - Centralizes environment variables and service settings.

---
This detailed overview provides all the necessary information for an LLM to understand the structure, components, and workflows within the assistant service.
