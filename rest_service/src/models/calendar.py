from typing import Optional
from datetime import datetime
from sqlmodel import Field, Relationship, SQLModel

class CalendarCredentials(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="telegramuser.id")
    access_token: str
    refresh_token: str
    token_expiry: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: Optional["TelegramUser"] = Relationship(back_populates="calendar_credentials") 