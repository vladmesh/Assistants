from datetime import datetime
from typing import Optional

from .base import BaseSchema, TimestampSchema


# Schema for storing/updating calendar credentials
class CalendarCredentialsBase(BaseSchema):
    user_id: int
    access_token: str
    refresh_token: str
    token_expiry: datetime


class CalendarCredentialsCreate(CalendarCredentialsBase):
    pass


# No specific update schema needed if all fields are always required for update
# class CalendarCredentialsUpdate(BaseSchema):
#    access_token: Optional[str] = None
#    refresh_token: Optional[str] = None
#    token_expiry: Optional[datetime] = None


# Schema for reading calendar credentials (output)
class CalendarCredentialsRead(CalendarCredentialsBase, TimestampSchema):
    id: int  # Internal DB ID
