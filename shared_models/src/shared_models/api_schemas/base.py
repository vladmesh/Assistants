from datetime import UTC, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)  # Import BaseModel from Pydantic

# from sqlmodel import SQLModel # Remove SQLModel import


# Base Pydantic model configuration
class BaseSchema(BaseModel):  # Inherit from pydantic.BaseModel
    # For Pydantic V2
    model_config = ConfigDict(
        from_attributes=True,  # Allows creating schemas from ORM models
        populate_by_name=True,  # Allows using alias for field names if defined
        # extra='forbid' # Uncomment to prevent extra fields in input
    )


# Base schema including standard timestamps
class TimestampSchema(BaseSchema):
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            # Assume naive datetime is UTC
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
