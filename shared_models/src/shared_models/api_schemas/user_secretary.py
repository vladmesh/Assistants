from uuid import UUID

from .assistant import AssistantRead  # Needed for nested read response
from .base import BaseSchema, TimestampSchema


# Schema for the link between User and Secretary (Assistant)
class UserSecretaryLinkBase(BaseSchema):
    user_id: int
    secretary_id: UUID
    is_active: bool = True


class UserSecretaryLinkCreate(UserSecretaryLinkBase):
    # Typically only IDs needed for creation, handled by path parameters usually
    # but defining allows validation if sent in body
    pass


# Update schema might not be needed if only activation/deactivation happens
# class UserSecretaryLinkUpdate(BaseSchema):
#     is_active: Optional[bool] = None


class UserSecretaryLinkRead(UserSecretaryLinkBase, TimestampSchema):
    id: UUID  # Internal DB ID of the link itself
    # Optional: Include nested secretary info if needed
    # secretary: Optional[AssistantRead] = None
