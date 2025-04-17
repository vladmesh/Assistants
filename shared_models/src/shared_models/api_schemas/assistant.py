import json
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator

# Need enums from models, adjust path if needed
# from models.assistant import AssistantType, ToolType
from ..enums import AssistantType, ToolType  # Import from shared_models.enums

# Assuming BaseSchema and TimestampSchema are in .base
from .base import BaseSchema, TimestampSchema

# ========== Tool Schemas ============


class ToolBase(BaseSchema):
    name: str
    tool_type: ToolType
    description: Optional[str] = None
    input_schema: Optional[dict] = None  # Store as dict
    assistant_id: Optional[UUID] = None  # For sub_assistant type
    is_active: bool = True

    @field_validator("input_schema", mode="before")
    @classmethod
    def parse_input_schema(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string for input_schema")
        # Allow None or dict
        if v is not None and not isinstance(v, dict):
            raise TypeError("input_schema must be a dict, a valid JSON string, or None")
        return v


class ToolCreate(ToolBase):
    pass


class ToolUpdate(BaseSchema):  # Allow partial updates
    name: Optional[str] = None
    tool_type: Optional[ToolType] = None
    description: Optional[str] = None
    input_schema: Optional[dict] = Field(
        default=None
    )  # Use Field to allow None explicitly on update
    assistant_id: Optional[UUID] = None
    is_active: Optional[bool] = None

    @field_validator("input_schema", mode="before")
    @classmethod
    def parse_update_input_schema(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON string for input_schema")
        # Allow None or dict
        if v is not None and not isinstance(v, dict):
            raise TypeError("input_schema must be a dict, a valid JSON string, or None")
        return v


class ToolRead(ToolBase, TimestampSchema):
    id: UUID


# ========= Assistant Schemas ==========


class AssistantBase(BaseSchema):
    name: str
    is_secretary: bool = False
    model: str
    instructions: Optional[str] = None
    assistant_type: AssistantType = AssistantType.LLM
    openai_assistant_id: Optional[str] = None  # Specific to OpenAI Assistants
    is_active: bool = True


class AssistantCreate(AssistantBase):
    pass


class AssistantUpdate(BaseSchema):  # Allow partial updates
    name: Optional[str] = None
    is_secretary: Optional[bool] = None
    model: Optional[str] = None
    instructions: Optional[str] = None
    assistant_type: Optional[AssistantType] = None
    openai_assistant_id: Optional[str] = None
    is_active: Optional[bool] = None


class AssistantRead(AssistantBase, TimestampSchema):
    id: UUID
    tools: List[ToolRead] = []  # Include linked tools in read schema


# ========= AssistantToolLink Schemas ==========
# Link between Assistant and Tool


class AssistantToolLinkBase(BaseSchema):
    assistant_id: UUID
    tool_id: UUID
    is_active: bool = True  # Assuming we might want soft deletes


class AssistantToolLinkCreate(AssistantToolLinkBase):
    # Only IDs needed for creation
    pass


# Read schema might just reuse the model or define specific fields
class AssistantToolLinkRead(AssistantToolLinkBase, TimestampSchema):
    id: UUID  # Assuming the link itself has an ID
    # Optionally include nested AssistantRead/ToolRead if needed for specific use cases
    # assistant: Optional[AssistantRead] = None
    # tool: Optional[ToolRead] = None


# ... existing code ...
