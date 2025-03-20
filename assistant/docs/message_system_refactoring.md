# Message System Refactoring

## Overview
This document describes the task of refactoring the message handling system between LLM, user, and tools in the assistant service.

## Current State
Currently, the system uses a basic message handling approach:

1. Message Types:
   - `HumanMessage` (inherited from LangChain's `HumanMessage`)
   - `AIMessage` (inherited from LangChain's `AIMessage`)
   - `MessagesThread` for storing conversation history

2. Message Flow:
   - Messages are received through Redis queue
   - Processed by `AssistantOrchestrator`
   - Passed to appropriate assistant (Secretary or SubAssistant)
   - Responses are sent back through Redis queue

3. Current Limitations:
   - No explicit timestamp information in messages
   - Limited message source identification
   - Basic message type system that doesn't fully represent all possible message sources

## Requirements

### 1. Message Timestamp
- Each message must include exact UTC timestamp
- Timestamp is automatically set at message creation time in the base class
- Must be consistent across all message types
- No need to pass timestamp in constructors

### 2. Message Source Types
Need to implement the following message sources:

1. Human
   - User messages (equivalent to LangChain's HumanMessage)
   - Direct user input to the system
   - Source is automatically set to `MessageSource.HUMAN`

2. Secretary
   - Responses to user from secretary assistant
   - Requests to sub-assistants through tools
   - Any communication initiated by secretary
   - Source is automatically set to `MessageSource.SECRETARY`

3. Tool
   - Responses from tools to secretary/assistants
   - Triggered notifications from tools
   - Any communication from tools
   - Source is automatically set to `MessageSource.TOOL`

4. System
   - System-level messages to LLM
   - Not related to specific tools or user interactions
   - Used for system context or configuration
   - Source is automatically set to `MessageSource.SYSTEM`

### 3. Message Type System
Current LangChain message types (`HumanMessage` and `AIMessage`) are insufficient. Need to:
- Define clear message type hierarchy
- Support all identified message sources
- Maintain compatibility with LangChain where possible
- Add metadata support for additional context
- Make source and timestamp internal fields of base class

### 4. Message Metadata
Initial metadata requirements:
- Source type (Human/Secretary/Tool/System) - internal field
- UTC timestamp - internal field
- Extensible metadata structure for future additions

### 5. Message Processing in Orchestrator
- Messages from Redis queue should include source information:
  ```python
  {
      "text": "Message content",
      "source": "tool",  # or "human", "system"
      "tool_name": "google_calendar",  # optional, for tool messages
      "user_id": "user123"
  }
  ```
- Orchestrator should create appropriate message type based on source:
  ```python
  if source == "tool":
      message = ToolMessage(content=text, tool_name=tool_name)
  elif source == "human":
      message = HumanMessage(content=text)
  elif source == "system":
      message = SystemMessage(content=text)
  ```
- All messages sent to LLM should be marked as "user" role in OpenAI format
- Message string representation should include source and timestamp for context

## Tasks Breakdown
1. Message Type System Redesign
   - Create new base message class with metadata support
   - Define specific message types for each source
   - Implement automatic timestamp handling
   - Add metadata structure with source and timestamp
   - Make source and timestamp internal fields

2. Message Processing Updates
   - Update message creation points
   - Modify message handling in orchestrator
   - Update assistant implementations
   - Update tool implementations

3. Storage and Thread Management
   - Update `MessagesThread` implementation
   - Modify message storage format
   - Update message retrieval logic

4. Testing and Validation
   - Add unit tests for new message types
   - Add integration tests for message flow
   - Validate timestamp handling
   - Test metadata support

## Technical Considerations
1. Backward Compatibility
   - Maintain compatibility with existing LangChain integration
   - Ensure smooth transition for existing code
   - Consider migration strategy for stored messages

2. Performance
   - Minimize overhead from additional metadata
   - Consider message size impact
   - Optimize message processing

3. Error Handling
   - Define error message types
   - Implement proper error propagation
   - Add validation for required fields

## Implementation Plan
1. Base Message Class
   - Implement internal timestamp field
   - Implement internal source field
   - Add metadata support
   - Add string representation for LLM

2. Message Types
   - Implement HumanMessage
   - Implement SecretaryMessage
   - Implement ToolMessage
   - Implement SystemMessage
   - Each type sets its own source automatically

3. Message Thread
   - Update to use new message types
   - Add timestamp tracking
   - Update storage format

4. Testing
   - Add unit tests for all message types
   - Test automatic timestamp and source setting
   - Validate string representation
   - Test thread functionality

## Testing Strategy
1. Unit Tests
   - Test message creation
   - Test timestamp generation
   - Test source setting
   - Test metadata handling
   - Test string representation

2. Integration Tests
   - Test message flow
   - Test thread management
   - Test storage and retrieval
   - Test LLM compatibility

## Migration Plan
1. Code Updates
   - Update message creation points
   - Update message handling
   - Update storage format

2. Data Migration
   - Convert existing messages
   - Update stored threads
   - Validate data integrity

3. Testing
   - Run full test suite
   - Validate message flow
   - Check LLM integration 