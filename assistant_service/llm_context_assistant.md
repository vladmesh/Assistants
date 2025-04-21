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

### 2.2 Directory Structure

```
assistant_service/src/
├── assistants/           # Assistant implementations
│   ├── factory.py       # Assistant factory
│   ├── langgraph/       # LangGraph implementation details
│   │   ├── langgraph_assistant.py  # Main LangGraphAssistant class
│   │   ├── graph_builder.py      # Logic for building the graph
│   │   ├── state.py              # Definition of AssistantState
│   │   ├── nodes/                # Graph node implementations (specific node logic might be in graph_builder or assistant class)
│   │   └── utils/                # Utility functions for the graph
│   │       └── token_counter.py
├── tools/               # Tool implementations
│   ├── base.py          # Base tool class
│   ├── factory.py       # Tool factory (creates tool instances)
│   ├── calendar.py      # Calendar operations
│   ├── reminder_tool.py # Reminder creation tool (ReminderTool)
│   ├── sub_assistant_tool.py # Sub-assistant wrapper (SubAssistantTool)
│   ├── time.py          # Time operations
│   └── web_search.py    # Web search using Tavily
├── services/          # External service clients
├── storage/           # Context storage
├── config/            # Service configuration
├── core/              # Core logic
├── utils/             # Utilities
└── orchestrator.py    # Main orchestrator
```

## 3. Implementation Details

### 3.1 LangGraph Implementation

#### Graph-Based Processing
- The `LangGraphAssistant` (in `assistants/langgraph/langgraph_assistant.py`) orchestrates message processing using a state machine defined by a LangGraph.
- The graph structure is built by the `build_full_graph` function in `assistants/langgraph/graph_builder.py`.
- The graph consists of several nodes that manage state transitions and processing:
    - `summarize` (Optional): Conditionally summarizes older messages if the context exceeds a limit.
    - `ensure_limit`: Explicitly truncates message history if it exceeds the maximum token limit, keeping essential messages.
    - `assistant`: The main agent logic node. It prepares the prompt (including system message and facts), calls the LLM, and determines the next action (respond or use a tool).
    - `tools`: Executes the chosen tool if the assistant node decides to use one.
- The state (`AssistantState` defined in `assistants/langgraph/state.py`) is persisted between turns using a checkpointer (e.g., `RestCheckpointSaver`).

#### Tool Integration
- Tools are implemented as classes inheriting from `BaseTool` (in `tools/`).
- Tool instances are created by `ToolFactory` (in `tools/factory.py`), which receives tool definitions from `rest_service` and injects necessary context (`user_id`, `assistant_id`).
- The initialized tools are passed to the `LangGraphAssistant` and made available to the `ToolNode` within the graph.
- Example tool: `UserFactTool` (in `tools/user_fact_tool.py`) is used by the agent to save facts about the user via the REST API.
```python
# Example of how ToolFactory might be used by AssistantFactory
async def create_langchain_tools(
    self, tool_definitions: List[ToolRead], user_id: str, assistant_id: str
) -> List[Tool]:
    tools = []
    for tool_def in tool_definitions:
        tool_class = self._get_tool_class(tool_def.tool_type)
        if tool_class:
            # ... (logic to prepare args for the specific tool class)
            tool_instance = tool_class(
                name=tool_def.name, 
                description=tool_def.description, 
                settings=self.settings, 
                user_id=user_id, 
                assistant_id=assistant_id,
                # ... other specific args
            )
            tools.append(tool_instance)
    return tools
```

## 4. Message & Context Handling

### 4.1 Message Types
- HumanMessage: User messages
- SecretaryMessage: Secretary responses
- ToolMessage: Tool execution results **and incoming reminder trigger events**
- SystemMessage: System notifications

### 4.2 Context Management
- LangGraph: Graph-based state management
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
    redis_url: str
    log_level: str
    tavily_api_key: Optional[str] = None
```

### 7.2 Environment Variables
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
    - Creates the `LangGraphAssistant` instance, providing it with the initialized tools, `RestServiceClient`, and checkpointer.
    - The `LangGraphAssistant` then internally calls `build_full_graph` to assemble its processing logic.
    - Also used internally by `ToolFactory` to instantiate sub-assistants required by `SubAssistantTool`.
- `ToolFactory` (internal instance):
    - Responsible for creating instances of specific tool classes (e.g., `ReminderTool`, `SubAssistantTool`) based on configuration from `rest_service`.
    - Injects necessary context (like `user_id`, `assistant_id`) into tool instances during their creation. 