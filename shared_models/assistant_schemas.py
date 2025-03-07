from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field, validator
from enum import Enum

class ResponseType(str, Enum):
    CHAT = "chat"
    CALENDAR = "calendar"
    WEATHER = "weather"
    TASK = "task"
    HEALTH = "health"
    GEOFENCE = "geofence"

class CalendarAction(str, Enum):
    CREATE_EVENT = "create_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"
    LIST_EVENTS = "list_events"

class WeatherAction(str, Enum):
    GET_FORECAST = "get_forecast"

class TaskAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"

class HealthAction(str, Enum):
    GET_STATS = "get_stats"
    GET_RECOMMENDATIONS = "get_recommendations"

class GeofenceAction(str, Enum):
    CREATE_ZONE = "create_zone"
    UPDATE_ZONE = "update_zone"
    DELETE_ZONE = "delete_zone"
    LIST_ZONES = "list_zones"

class Period(str, Enum):
    TODAY = "today"
    TOMORROW = "tomorrow"
    WEEK = "week"
    DAY = "day"
    MONTH = "month"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Metric(str, Enum):
    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    HUMIDITY = "humidity"
    ACTIVITY = "activity"
    SLEEP = "sleep"
    HEART_RATE = "heart_rate"

class Trigger(str, Enum):
    ENTER = "enter"
    EXIT = "exit"

class Event(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    location: Optional[str] = None

class Task(BaseModel):
    title: str
    due_date: datetime
    description: Optional[str] = None
    priority: Optional[Priority] = None

class Zone(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius: float
    triggers: Optional[List[Trigger]] = None

class AssistantMetadata(BaseModel):
    user_id: str
    timestamp: datetime
    context: Optional[dict] = None

class AssistantData(BaseModel):
    message: Optional[str] = None
    action: Optional[Union[CalendarAction, WeatherAction, TaskAction, HealthAction, GeofenceAction]] = None
    event: Optional[Event] = None
    location: Optional[str] = None
    period: Optional[Period] = None
    metrics: Optional[List[Metric]] = None
    task: Optional[Task] = None
    zone: Optional[Zone] = None

    @validator('action')
    def validate_action_type(cls, v, values):
        if v is None:
            return v
        # Validate action type matches the data structure
        if isinstance(v, CalendarAction) and not values.get('event'):
            raise ValueError("Calendar action requires event data")
        if isinstance(v, WeatherAction) and not values.get('location'):
            raise ValueError("Weather action requires location")
        if isinstance(v, TaskAction) and not values.get('task'):
            raise ValueError("Task action requires task data")
        if isinstance(v, GeofenceAction) and not values.get('zone'):
            raise ValueError("Geofence action requires zone data")
        return v

class AssistantResponse(BaseModel):
    type: ResponseType
    data: AssistantData
    metadata: AssistantMetadata

    @validator('type')
    def validate_response_type(cls, v, values):
        if v == ResponseType.CHAT and not values.get('data', {}).get('message'):
            raise ValueError("Chat response requires message")
        return v 