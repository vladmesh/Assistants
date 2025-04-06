# Assistant Service Detailed Overview

## 1. Overview
The assistant service is the core engine of the Smart Assistant project. It handles:
- Processing of incoming user messages
- Management of conversation context
- Coordination of tool invocations
- Asynchronous message processing via Redis queues
- Supporting multiple secretary instances
- Maintaining context isolation between users

## 2. Architecture

### 2.1 Core Components

#### BaseLLMChat (LangGraph)
- Primary implementation using LangGraph
- Message processing graph
- Built-in tool support
- Complex interaction scenarios

#### OpenAIAssistant (OpenAI Assistants API)
- Secondary implementation using OpenAI API
- Thread-based context
- Tool orchestration
- Asynchronous processing

### 2.2 Directory Structure

```
assistant_service/src/
├── assistants/           # Assistant implementations
│   ├── base.py          # Base assistant class
│   ├── factory.py       # Assistant factory
│   ├── langgraph.py     # LangGraph implementation
│   └── openai.py        # OpenAI implementation
├── tools/               # Tool implementations
│   ├── base.py         # Base tool class
│   ├── calendar.py     # Calendar operations
│   ├── reminder.py     # Reminder creation tool (create_reminder)
│   ├── rest.py         # REST service interface (UNUSED? Verify)
│   ├── sub_assistant.py # Sub-assistant wrapper
│   ├── time.py         # Time operations
│   └── web_search.py   # Web search using Tavily
├── messages/           # Message handling
│   ├── base.py        # Base message class
│   └── types.py       # Message types
├── services/          # External service clients
├── storage/           # Context storage
├── config/            # Service configuration
├── core/              # Core logic
├── utils/             # Utilities
└── orchestrator.py    # Main orchestrator
```

## 3. Implementation Details

### 3.1 LangGraph Implementation

#### Message Processing
```python
class BaseLLMChat(BaseAssistant):
    def __init__(self, settings: Settings, is_secretary: bool = False):
        self.settings = settings
        self.is_secretary = is_secretary
        self.agent = None
```

#### Tool Integration
```python
def initialize_tools(self, secretary_id: str):
    secretary_tools = await self.rest_client.get_assistant_tools(secretary_id)
    tools = []
    for tool_data in secretary_tools:
        rest_tool = RestServiceTool(**tool_data.dict(), settings=self.settings)
        tool = rest_tool.to_tool(secretary_id=secretary_id)
        tools.append(tool)
    return tools

# Example tool: create_reminder (tools/reminder_tool.py)
# - Args: type ('one_time'/'recurring'), payload (JSON string), 
#         trigger_at+timezone (for one_time), cron_expression (for recurring)
# - Action: Calls POST /api/reminders/ in rest_service
```

### 3.2 OpenAI Implementation

#### Thread Management
```python
class OpenAIAssistant(BaseAssistant):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
```

#### Tool Registration
```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "calendar_create",
            "description": "Create a calendar event",
            "parameters": {...}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for information on a specific topic",
            "parameters": {...}
        }
    }
]
```

## 4. Message & Context Handling

### 4.1 Message Types
- HumanMessage: User messages
- SecretaryMessage: Secretary responses
- ToolMessage: Tool execution results **and incoming reminder trigger events**
- SystemMessage: System notifications

### 4.2 Context Management
- LangGraph: Graph-based state management
- OpenAI: Thread-based storage
- Redis: Persistent storage and queues

## 5. External Integration

### 5.1 Redis
- Input Queue (`REDIS_QUEUE_TO_SECRETARY` env var): Receives `HumanMessage` (from Telegram) and `reminder_triggered` events (from `cron_service`).
- Output Queue (`REDIS_QUEUE_TO_TELEGRAM` env var): Sends assistant responses to `telegram_bot_service`.
- Context storage (potentially, if implemented).
- State management (potentially, if implemented).

### 5.2 External Services
- REST API service
- Google Calendar service
- Telegram Bot service
- Tavily API for web search

## 6. Error Handling & Logging

### 6.1 Error Management
- Structured error handling
- Retry mechanisms
- Graceful degradation

### 6.2 Logging
- Request tracing
- Error logging
- Performance monitoring

## 7. Configuration

### 7.1 Settings
```python
class Settings(BaseSettings):
    openai_api_key: str
    redis_url: str
    log_level: str
    tavily_api_key: Optional[str] = None
```

### 7.2 Environment Variables
- API keys
- Service URLs
- Logging settings

## 8. Development Guidelines

### 8.1 Adding New Tools
- Extend BaseTool
- Implement _execute method
- Add error handling
- Update documentation

### 8.2 Testing
- Unit tests for tools
- Integration tests
- Performance tests

### 8.3 Best Practices
- Use type hints
- Follow naming conventions
- Document changes
- Maintain test coverage

## Orchestrator (`orchestrator.py`)
- Listens to the input Redis queue (`listen_for_messages`).
- **Handles Incoming Messages:**
  - If message is a `reminder_triggered` event:
    - Calls `handle_reminder_trigger`.
    - Extracts `user_id`.
    - Retrieves the user's current secretary using `factory.get_user_secretary(user_id)`.
    - Constructs a `ToolMessage` with `tool_name="reminder_trigger"` and event details.
    - Calls `secretary.process_message` with the `ToolMessage`.
    - Sends the secretary's response to the output Redis queue.
  - If message is a standard `QueueMessage` (`HUMAN` or `TOOL` type):
    - Calls `process_message`.
    - Parses `QueueMessage`.
    - Retrieves or creates the user's secretary using `factory.get_user_secretary(user_id)`.
    - Converts `QueueMessage` to `HumanMessage` or `ToolMessage`.
    - Calls `secretary.process_message`.
    - Sends the secretary's response to the output Redis queue.

## Assistant Factory (`assistants/factory.py`)
- `get_user_secretary(user_id)`: Retrieves/caches the secretary assistant for a given user.
- `get_assistant_by_id(uuid)`: Retrieves an assistant instance by its UUID (used internally, e.g., for sub-assistants).
- `initialize_tools(secretary_id)`: Fetches tool configurations from `rest_service` and initializes tool instances, **passing `secretary_id` to the tool constructors (e.g., for `ReminderTool`)**. 