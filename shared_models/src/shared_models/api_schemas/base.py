from datetime import datetime

from pydantic import BaseModel, ConfigDict  # Import BaseModel from Pydantic

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
