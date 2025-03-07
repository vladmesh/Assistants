from datetime import datetime, timedelta
from assistant_schemas import (
    AssistantResponse,
    ResponseType,
    AssistantData,
    AssistantMetadata,
    CalendarAction,
    Event,
    WeatherAction,
    Period,
    Metric,
    TaskAction,
    Task,
    Priority,
    HealthAction
)

# Example 1: Chat Response
chat_response = AssistantResponse(
    type=ResponseType.CHAT,
    data=AssistantData(
        message="Привет! Как я могу помочь?"
    ),
    metadata=AssistantMetadata(
        user_id="123456789",
        timestamp=datetime.utcnow()
    )
)

# Example 2: Calendar Event
calendar_response = AssistantResponse(
    type=ResponseType.CALENDAR,
    data=AssistantData(
        action=CalendarAction.CREATE_EVENT,
        event=Event(
            title="Встреча с клиентом",
            start_time=datetime.utcnow() + timedelta(days=1),
            end_time=datetime.utcnow() + timedelta(days=1, hours=1),
            description="Обсуждение нового проекта",
            location="Офис"
        )
    ),
    metadata=AssistantMetadata(
        user_id="123456789",
        timestamp=datetime.utcnow()
    )
)

# Example 3: Weather Query
weather_response = AssistantResponse(
    type=ResponseType.WEATHER,
    data=AssistantData(
        action=WeatherAction.GET_FORECAST,
        location="Москва",
        period=Period.TOMORROW,
        metrics=[Metric.TEMPERATURE, Metric.PRECIPITATION, Metric.HUMIDITY]
    ),
    metadata=AssistantMetadata(
        user_id="123456789",
        timestamp=datetime.utcnow()
    )
)

# Example 4: Task Creation
task_response = AssistantResponse(
    type=ResponseType.TASK,
    data=AssistantData(
        action=TaskAction.CREATE,
        task=Task(
            title="Подготовить отчет",
            description="Еженедельный отчет по проекту",
            due_date=datetime.utcnow() + timedelta(days=7),
            priority=Priority.HIGH
        )
    ),
    metadata=AssistantMetadata(
        user_id="123456789",
        timestamp=datetime.utcnow()
    )
)

# Example 5: Health Data Query
health_response = AssistantResponse(
    type=ResponseType.HEALTH,
    data=AssistantData(
        action=HealthAction.GET_STATS,
        period=Period.WEEK,
        metrics=[Metric.ACTIVITY, Metric.SLEEP, Metric.HEART_RATE]
    ),
    metadata=AssistantMetadata(
        user_id="123456789",
        timestamp=datetime.utcnow()
    )
)

# Example of converting to JSON
def print_examples():
    print("Chat Response:")
    print(chat_response.json(indent=2))
    print("\nCalendar Response:")
    print(calendar_response.json(indent=2))
    print("\nWeather Response:")
    print(weather_response.json(indent=2))
    print("\nTask Response:")
    print(task_response.json(indent=2))
    print("\nHealth Response:")
    print(health_response.json(indent=2))

if __name__ == "__main__":
    print_examples() 