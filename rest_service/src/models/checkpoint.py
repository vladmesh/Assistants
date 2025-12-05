import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, LargeBinary, String, func
from sqlmodel import Field

from .base import BaseModel  # Import from local base


class Checkpoint(BaseModel, table=True):
    __tablename__ = "checkpoints"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs={
            "server_default": func.gen_random_uuid(),
            "unique": True,
            "nullable": False,
            "index": True,
        },
    )
    thread_id: str = Field(sa_column=Column(String, nullable=False, index=True))
    checkpoint_blob: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    checkpoint_metadata: dict | None = Field(
        sa_column=Column(JSON, nullable=True), alias="metadata"
    )

    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
