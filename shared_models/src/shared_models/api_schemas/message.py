from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field

from .base import BaseSchema


class MessageBase(BaseSchema):
    user_id: int
    assistant_id: UUID
    role: str = Field(
        ...,
        description="Role of the message sender (e.g., 'user', 'assistant', 'system', 'tool_request', 'tool_response')",
    )
    content: str
    content_type: str = Field(
        default="text", description="Content type of the message (e.g., 'text', 'json')"
    )
    tool_call_id: Optional[str] = None
    status: str = Field(
        default="active",
        description="Status of the message (e.g., 'active', 'summarized', 'archived', 'error')",
    )
    summary_id: Optional[int] = None
    meta_data: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    pass


class MessageRead(MessageBase):
    id: int
    timestamp: datetime
    # orm_mode is handled by model_config = ConfigDict(from_attributes=True) in BaseSchema


class MessageUpdate(BaseSchema):
    status: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
    summary_id: Optional[int] = None
    # Other fields (role, content, content_type, tool_call_id) are not updatable via this schema as per plan.
