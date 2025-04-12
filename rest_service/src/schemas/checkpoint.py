import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CheckpointBase(BaseModel):
    thread_id: str
    checkpoint_data_base64: str  # Pass binary data as base64 string in JSON
    checkpoint_metadata: Optional[Dict[str, Any]] = None


class CheckpointCreate(CheckpointBase):
    pass


class CheckpointRead(CheckpointBase):
    id: uuid.UUID
    updated_at: datetime
    created_at: datetime

    class Config:
        # For Pydantic V1
        # orm_mode = True
        # For Pydantic V2
        from_attributes = True
