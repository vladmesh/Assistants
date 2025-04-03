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
│   ├── reminder.py     # Reminder management
│   ├── rest.py         # REST service interface
│   ├── sub_assistant.py # Sub-assistant wrapper
│   └── time.py         # Time operations
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
def _initialize_tools(self):
    tools = [
        TimeToolWrapper(),
        CalendarCreateTool(settings=self.settings),
        CalendarListTool(settings=self.settings),
        SubAssistantTool(settings=self.settings)
    ]
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
    }
]
```

## 4. Message & Context Handling

### 4.1 Message Types
- HumanMessage: User messages
- SecretaryMessage: Secretary responses
- ToolMessage: Tool execution results
- SystemMessage: System notifications

### 4.2 Context Management
- LangGraph: Graph-based state management
- OpenAI: Thread-based storage
- Redis: Persistent storage and queues

## 5. External Integration

### 5.1 Redis
- Message queues
- Context storage
- State management

### 5.2 External Services
- REST API service
- Google Calendar service
- Telegram Bot service

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