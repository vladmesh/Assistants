import logging
from typing import List, Optional

from models.user import TelegramUser
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# from schemas import TelegramUserCreate, TelegramUserUpdate
from shared_models.api_schemas import TelegramUserCreate, TelegramUserUpdate

logger = logging.getLogger(__name__)


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[TelegramUser]:
    """Get a user by their internal database ID."""
    user = await db.get(TelegramUser, user_id)
    return user


async def get_user_by_telegram_id(
    db: AsyncSession, telegram_id: int
) -> Optional[TelegramUser]:
    """Get a user by their Telegram ID."""
    query = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_users(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> List[TelegramUser]:
    """Get a list of users with pagination."""
    query = select(TelegramUser).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_user(db: AsyncSession, user_in: TelegramUserCreate) -> TelegramUser:
    """Create a new user."""
    # Check if user already exists by telegram_id
    existing_user = await get_user_by_telegram_id(db, user_in.telegram_id)
    if existing_user:
        logger.warning(
            f"Attempted to create user with existing telegram_id: {user_in.telegram_id}"
        )
        # Depending on requirements, either return the existing user or raise an error
        # For now, let's raise an error to prevent duplicates explicitly
        raise ValueError(f"User with telegram_id {user_in.telegram_id} already exists.")
        # return existing_user

    db_user = TelegramUser.model_validate(
        user_in
    )  # Use model_validate for Pydantic v2 compatibility
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    logger.info(
        f"User created with telegram_id: {db_user.telegram_id}, ID: {db_user.id}"
    )
    return db_user


async def update_user(
    db: AsyncSession, user_id: int, user_in: TelegramUserUpdate
) -> Optional[TelegramUser]:
    """Update an existing user by their internal database ID."""
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        logger.warning(f"Attempted to update non-existent user ID: {user_id}")
        return None

    update_data = user_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.add(db_user)  # Add to session to track changes
    await db.commit()
    await db.refresh(db_user)
    logger.info(f"User updated with ID: {db_user.id}")
    return db_user


async def delete_user(db: AsyncSession, user_id: int) -> bool:
    """Delete a user by their internal database ID."""
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        logger.warning(f"Attempted to delete non-existent user ID: {user_id}")
        return False

    await db.delete(db_user)
    await db.commit()
    logger.info(f"User deleted with ID: {user_id}")
    return True
