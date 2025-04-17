import logging
from datetime import datetime
from typing import Optional

from models.calendar import CalendarCredentials
from models.user import TelegramUser  # Needed to check user existence
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import CalendarCredentialsCreate  # Use Create for input

logger = logging.getLogger(__name__)


async def get_credentials(
    db: AsyncSession, user_id: int
) -> Optional[CalendarCredentials]:
    """Get calendar credentials for a user."""
    result = await db.execute(
        select(CalendarCredentials).where(CalendarCredentials.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_or_update_credentials(
    db: AsyncSession, user_id: int, creds_in: CalendarCredentialsCreate
) -> CalendarCredentials:
    """Create or update calendar credentials for a user."""
    # Verify user exists
    user = await db.get(TelegramUser, user_id)
    if not user:
        logger.error(f"User not found when trying to update credentials: {user_id}")
        raise ValueError("User not found")  # Or a more specific exception

    credentials = await get_credentials(db, user_id)

    if not credentials:
        logger.info(f"Creating new calendar credentials for user {user_id}")
        credentials = CalendarCredentials(
            user_id=user_id,
            access_token=creds_in.access_token,
            refresh_token=creds_in.refresh_token,
            token_expiry=creds_in.token_expiry,
        )
        db.add(credentials)
    else:
        logger.info(f"Updating existing calendar credentials for user {user_id}")
        credentials.access_token = creds_in.access_token
        credentials.refresh_token = creds_in.refresh_token
        credentials.token_expiry = creds_in.token_expiry
        credentials.updated_at = datetime.utcnow()  # Manually update timestamp
        db.add(credentials)  # Add to session to track changes

    await db.commit()
    await db.refresh(credentials)
    logger.info(f"Successfully updated/created calendar credentials for user {user_id}")
    return credentials


async def delete_credentials(db: AsyncSession, user_id: int) -> bool:
    """Delete calendar credentials for a user."""
    credentials = await get_credentials(db, user_id)
    if not credentials:
        logger.warning(f"No calendar credentials found to delete for user {user_id}")
        return False

    await db.delete(credentials)
    await db.commit()
    logger.info(f"Successfully deleted calendar credentials for user {user_id}")
    return True
