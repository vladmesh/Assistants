from datetime import datetime

from pydantic import ConfigDict
from sqlmodel import SQLModel


class BaseSchema(SQLModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime
