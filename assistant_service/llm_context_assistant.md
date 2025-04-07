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

#### LangGraphAssistant (LangGraph)
- The primary and currently active implementation using LangGraph.
- Responsible for the main message processing graph.
- Provides built-in support for tool integration and execution.
- Handles complex conversational flows and state management via checkpoints.

#### OpenAIAssistant (OpenAI Assistants API) - Deprecated/Experimental
- Previous or experimental implementation using the OpenAI Assistants API.
- Not actively used in the current primary workflow managed by `AssistantFactory`.
- Code might still exist (`assistants/openai.py`) but is not the default choice.

### 2.2 Directory Structure

```
assistant_service/src/
├── assistants/           # Assistant implementations
│   ├── base.py          # Base assistant class
│   ├── factory.py       # Assistant factory
│   ├── langgraph.py     # LangGraph implementation
│   └── openai.py        # OpenAI implementation (Deprecated/Experimental)
├── tools/               # Tool implementations
│   ├── base.py          # Base tool class
│   ├── factory.py       # Tool factory (creates tool instances)
│   ├── calendar.py      # Calendar operations
│   ├── reminder_tool.py # Reminder creation tool (ReminderTool)
│   ├── sub_assistant_tool.py # Sub-assistant wrapper (SubAssistantTool)
│   ├── time.py          # Time operations
│   └── web_search.py    # Web search using Tavily
├── messages/            # Message handling
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

# Example tool: ReminderTool (tools/reminder_tool.py, default name 'create_reminder')
# - Args (Validated by ReminderSchema):
#   - type: str ('one_time'/'recurring')
#   - payload: str (JSON string with reminder content)
#   - trigger_at: Optional[str] (ISO format 'YYYY-MM-DD HH:MM' for 'one_time')
#   - timezone: Optional[str] (e.g., 'Europe/Moscow', required with trigger_at)
#   - cron_expression: Optional[str] (CRON format for 'recurring')
# - Context Args (set by ToolFactory):
#   - user_id: str (required for API call)
#   - assistant_id: str (required for API call)
# - Action: Calls POST /api/reminders/ in rest_service using validated data and context args.
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
- Initializes and holds an instance of `ToolFactory` (`tools/factory.py`).
- `get_user_secretary(user_id)`: Retrieves/caches the secretary assistant instance for a given user. Fetches configuration via REST and uses `get_assistant_by_id` to instantiate.
- `get_assistant_by_id(assistant_uuid, user_id)`: Retrieves an assistant instance by its UUID.
    - Fetches assistant configuration and tool *definitions* from `rest_service`.
    - Requires `user_id` for context.
    - Uses the internal `ToolFactory` instance (`tool_factory.create_langchain_tools`) to create actual tool instances from the definitions, passing `user_id` and `assistant_id` for context.
    - Creates the `LangGraphAssistant` instance, providing it with the initialized tools.
    - Also used internally by `ToolFactory` to instantiate sub-assistants required by `SubAssistantTool`.
- `ToolFactory` (internal instance):
    - Responsible for creating instances of specific tool classes (e.g., `ReminderTool`, `SubAssistantTool`) based on configuration from `rest_service`.
    - Injects necessary context (like `user_id`, `assistant_id`) into tool instances during their creation. 