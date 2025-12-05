from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from .base import BaseSchema


class MessageBase(BaseSchema):
    user_id: int
    assistant_id: UUID
    role: str = Field(
        ...,
        description=(
            "Role of the sender: user/assistant/system/tool_request/tool_response"
        ),
    )
    content: str
    content_type: str = Field(
        default="text", description="Content type of the message (e.g., 'text', 'json')"
    )
    tool_call_id: str | None = None
    status: str = Field(
        default="active",
        description="Message status: active/summarized/archived/error",
    )
    summary_id: int | None = None
    meta_data: dict[str, Any] | None = None


class MessageCreate(MessageBase):
    pass


class MessageRead(MessageBase):
    id: int
    timestamp: datetime
    # orm_mode handled via model_config=ConfigDict(from_attributes=True) in BaseSchema


class MessageUpdate(BaseSchema):
    status: str | None = None
    meta_data: dict[str, Any] | None = None
    summary_id: int | None = None
    # role/content/content_type/tool_call_id are not updatable via this schema
