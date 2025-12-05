from uuid import UUID

# Need enums from models, adjust path if needed
# from models.assistant import AssistantType, ToolType
from ..enums import AssistantType, ToolType  # Import from shared_models.enums

# Assuming BaseSchema and TimestampSchema are in .base
from .base import BaseSchema, TimestampSchema

# ========== Tool Schemas ============


class ToolBase(BaseSchema):
    name: str
    tool_type: ToolType
    description: str | None = None
    assistant_id: UUID | None = None  # For sub_assistant type
    is_active: bool = True


class ToolCreate(ToolBase):
    pass


class ToolUpdate(BaseSchema):  # Allow partial updates
    name: str | None = None
    tool_type: ToolType | None = None
    description: str | None = None
    assistant_id: UUID | None = None
    is_active: bool | None = None


class ToolRead(ToolBase, TimestampSchema):
    id: UUID


# ========= Assistant Schemas ==========


class AssistantBase(BaseSchema):
    name: str
    is_secretary: bool = False
    model: str
    instructions: str | None = None
    description: str | None = None
    startup_message: str | None = None
    assistant_type: AssistantType = AssistantType.LLM
    is_active: bool = True


class AssistantCreate(AssistantBase):
    pass


class AssistantUpdate(BaseSchema):  # Allow partial updates
    name: str | None = None
    is_secretary: bool | None = None
    model: str | None = None
    instructions: str | None = None
    description: str | None = None
    startup_message: str | None = None
    assistant_type: AssistantType | None = None
    is_active: bool | None = None


class AssistantRead(AssistantBase, TimestampSchema):
    id: UUID
    tools: list[ToolRead] = []  # Include linked tools in read schema


# A simpler version for creation response, without tools
class AssistantReadSimple(AssistantBase, TimestampSchema):
    id: UUID
    description: str | None = None


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
