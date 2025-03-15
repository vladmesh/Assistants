from typing import Optional, List
from sqlmodel import Field, Relationship
from sqlalchemy import Column, BigInteger
from .base import BaseModel

class TelegramUser(BaseModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int = Field(sa_column=Column(BigInteger, unique=True, nullable=False))
    username: Optional[str]
    
    # Relationships
    tasks: List["Task"] = Relationship(back_populates="user")
    cronjobs: List["CronJob"] = Relationship(back_populates="user")
    calendar_credentials: Optional["CalendarCredentials"] = Relationship(back_populates="user") 