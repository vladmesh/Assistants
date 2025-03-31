from datetime import datetime, UTC
from sqlmodel import SQLModel, Field
from sqlalchemy import event, TIMESTAMP


def get_utc_now() -> datetime:
    """Get current UTC time without timezone info"""
    return datetime.now(UTC).replace(tzinfo=None)


class BaseModel(SQLModel):
    created_at: datetime = Field(
        default_factory=get_utc_now, nullable=False, sa_type=TIMESTAMP(timezone=False)
    )
    updated_at: datetime = Field(
        default_factory=get_utc_now, nullable=False, sa_type=TIMESTAMP(timezone=False)
    )


# События для автоматического обновления
@event.listens_for(BaseModel, "before_update", propagate=True)
def before_update(mapper, connection, target):
    target.updated_at = get_utc_now()
