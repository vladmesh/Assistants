# Shared Models

Shared Pydantic models for Smart Assistant project.

## Installation

```bash
poetry add shared-models
```

## Usage

```python
from shared_models import QueueMessage, QueueMessageContent, QueueMessageSource, QueueMessageType

# Create a message
content = QueueMessageContent(message="Hello", metadata={"key": "value"})
message = QueueMessage(
    type=QueueMessageType.TOOL,
    user_id=1,
    source=QueueMessageSource.USER,
    content=content,
)

# Serialize to dict
data = message.to_dict()

# Deserialize from dict
restored = QueueMessage.from_dict(data)
```

## Development

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Run tests:
   ```bash
   poetry run pytest
   ```

3. Format code:
   ```bash
   poetry run black .
   poetry run isort .
   ```

4. Type checking:
   ```bash
   poetry run mypy .
   ```

## Models

### QueueMessage
Base class for all queue messages.

### QueueMessageContent
Content of queue message with metadata.

### QueueMessageType
Enum for message types:
- TOOL
- HUMAN

### QueueMessageSource
Enum for message sources:
- CRON
- CALENDAR
- USER

### ToolQueueMessage
Message from tool with tool name.

### HumanQueueMessage
Message from user with chat ID. 