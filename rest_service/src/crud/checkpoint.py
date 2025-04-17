import base64
import logging
from typing import Any, Dict, Optional

# Use absolute import for models
from models.checkpoint import Checkpoint
from sqlalchemy import desc, select
from sqlmodel import Session  # Use SQLModel session for async
from sqlmodel.ext.asyncio.session import AsyncSession

# from schemas.checkpoint import CheckpointCreate  # Keep absolute import
from shared_models.api_schemas import CheckpointCreate  # Use shared schema


async def create_checkpoint(
    db: AsyncSession,
    thread_id: str,
    checkpoint_data: bytes,
    checkpoint_metadata: Optional[Dict[str, Any]],  # Add metadata parameter
) -> Checkpoint:
    db_checkpoint = Checkpoint(
        thread_id=thread_id,
        checkpoint_blob=checkpoint_data,
        checkpoint_metadata=checkpoint_metadata,  # Save metadata
    )
    db.add(db_checkpoint)
    await db.commit()
    await db.refresh(db_checkpoint)
    return db_checkpoint


async def get_latest_checkpoint(
    db: AsyncSession, thread_id: str
) -> Optional[Checkpoint]:
    stmt = (
        select(Checkpoint)
        .where(Checkpoint.thread_id == thread_id)
        .order_by(desc(Checkpoint.created_at))  # Or updated_at, depending on logic
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first()
