from pydantic import BaseModel
from typing import Optional, Literal

class CronJobCreate(BaseModel):
    name: str
    type: Literal["notification", "schedule"]
    cron_expression: str
    user_id: int

class CronJobUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[Literal["notification", "schedule"]] = None
    cron_expression: Optional[str] = None

class CronJobResponse(BaseModel):
    id: int
    name: str
    type: Literal["notification", "schedule"]
    cron_expression: str
    user_id: int
    created_at: str
    updated_at: str
