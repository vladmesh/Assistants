# Smart Assistant

## Project Goal
Develop a virtual assistant capable of engaging in natural language dialogue and executing tasks via API integrations. The initial version focuses on:

- Google Calendar: Event management and reminders
- Weather: Real-time weather information and forecasts
- Tasks: Task management and reminders
- Health Data: Integration with health monitoring devices
- Geofencing: Location-based automation

## Main Interface
Telegram Bot – a user-friendly and accessible entry point for users.

## Features

### Google Calendar
- Create, edit, and delete events based on natural language requests
- Automatic reminders and notifications
- Support for recurring events

### Weather
- Current weather conditions
- Weather forecasts
- Location-based weather updates

### Tasks
- Create and manage tasks
- Set priorities and deadlines
- Track task completion

### Health Data
- Integration with health monitoring devices
- Activity tracking
- Health data analysis

### Geofencing
- Location-based triggers
- Automated notifications
- Custom location zones

## Technical Architecture

### Core Components
- **Programming Language**: Python
- **LLM Framework**: LangChain
- **Chat Models**: 
  - OpenAI GPT-4 (для сложных задач и рассуждений)
  - GPT-3.5-turbo (для простых запросов)
  - GPT-3.5-turbo-16k (для задач с большим контекстом)
- **Web Framework**: FastAPI
- **Message Queue**: Redis
- **Database**: PostgreSQL
- **Container Platform**: Docker

### Service Architecture
- **Assistant Service**: 
  - Core service using LangChain and OpenAI
  - Handles natural language processing
  - Manages tool execution
- **REST Service**: 
  - External API integrations
  - Data persistence
  - Business logic
- **Telegram Bot**: 
  - User interface
  - Message handling
- **Notification Service**: 
  - Manages notifications
  - Handles alerts
- **Cron Service**: 
  - Scheduled tasks
  - Recurring jobs

### Request Flow
1. User sends a message to the Telegram Bot
2. Message is queued in Redis
3. Assistant Service processes the message using LangChain and GPT-4
4. Based on the intent:
   - Direct response: returns text to user
   - Tool execution: calls appropriate service
5. Response is sent back through Redis queue
6. Bot delivers the response to user

### LangChain Configuration
The Assistant uses:
- Custom tools for each service integration
- Conversation memory for context
- Structured output parsing
- Error handling and retry logic

## Development Status

### Completed
1. Basic service architecture
2. LangChain integration
3. Redis message queuing
4. Calendar tool implementation

### In Progress
1. Weather integration
2. Task management
3. Health data collection
4. Geofencing system

### Planned
1. User preferences
2. Advanced notifications
3. Analytics and reporting
4. Multi-language support

## Advantages
- **Natural Language**: Гибкое использование различных моделей OpenAI
- **Модульный дизайн**: Easy to add new tools and services
- **Scalable**: Independent service scaling
- **Maintainable**: Clean code structure
- **Reliable**: Queue-based architecture

## Future Enhancements
- Voice interface
- Mobile app
- Additional LLM providers
- Smart home integration
- Advanced analytics
