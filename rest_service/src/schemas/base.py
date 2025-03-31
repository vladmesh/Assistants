from sqlmodel import SQLModel
from pydantic import ConfigDict
from datetime import datetime
from typing import Optional


class BaseSchema(SQLModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime 