from datetime import datetime, UTC
from sqlmodel import SQLModel, Field
from sqlalchemy import event

class BaseModel(SQLModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), nullable=False)

# События для автоматического обновления
@event.listens_for(BaseModel, "before_update", propagate=True)
def before_update(mapper, connection, target):
    target.updated_at = datetime.now(UTC) 