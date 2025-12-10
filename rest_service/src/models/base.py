from datetime import UTC, datetime

from sqlalchemy import TIMESTAMP, event
from sqlmodel import Field, SQLModel


def get_utc_now() -> datetime:
    """Return aware UTC timestamp"""
    return datetime.now(UTC)


class BaseModel(SQLModel):
    created_at: datetime = Field(
        default_factory=get_utc_now, nullable=False, sa_type=TIMESTAMP(timezone=True)
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, nullable=False, sa_type=TIMESTAMP(timezone=True)
    )


# События для автоматического обновления
@event.listens_for(BaseModel, "before_update", propagate=True)
def before_update(mapper, connection, target):
    target.updated_at = get_utc_now()
