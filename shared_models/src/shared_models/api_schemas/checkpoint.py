import uuid
from typing import Any, Dict, Optional

# Assuming BaseSchema and TimestampSchema are in .base
from .base import BaseSchema, TimestampSchema


class CheckpointBase(BaseSchema):
    thread_id: str
    checkpoint_data_base64: str  # Pass binary data as base64 string in JSON
    checkpoint_metadata: Optional[Dict[str, Any]] = None


class CheckpointCreate(CheckpointBase):
    pass


class CheckpointRead(CheckpointBase, TimestampSchema):
    id: uuid.UUID
    # updated_at and created_at are inherited from TimestampSchema
