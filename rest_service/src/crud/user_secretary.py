import logging
from typing import List, Optional
from uuid import UUID

from models.assistant import Assistant  # To check if assistant is secretary
from models.user import TelegramUser  # To check user existence
from models.user_secretary import UserSecretaryLink
from sqlalchemy.orm import selectinload  # Import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import UserSecretaryLinkCreate, UserSecretaryLinkRead

logger = logging.getLogger(__name__)


async def get_active_secretary_for_user(
    db: AsyncSession, user_id: int
) -> Optional[Assistant]:
    """Get the active secretary assistant assigned to a user, eagerly loading tools."""
    query = (
        select(Assistant)
        .join(UserSecretaryLink, UserSecretaryLink.secretary_id == Assistant.id)
        .where(UserSecretaryLink.user_id == user_id)
        .where(UserSecretaryLink.is_active == True)
        .where(Assistant.is_secretary == True)
        .options(selectinload(Assistant.tools))  # Eagerly load tools
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def assign_secretary_to_user(
    db: AsyncSession, user_id: int, secretary_id: UUID
) -> UserSecretaryLink:
    """Assign a secretary to a user. Deactivates any existing assignments."""
    # Check if user exists
    user = await db.get(TelegramUser, user_id)
    if not user:
        logger.error(f"User not found when assigning secretary: {user_id}")
        raise ValueError("User not found")

    # Check if assistant exists and is a secretary
    secretary = await db.get(Assistant, secretary_id)
    if not secretary:
        logger.error(f"Secretary assistant not found: {secretary_id}")
        raise ValueError("Secretary assistant not found")
    if not secretary.is_secretary:
        logger.error(f"Assistant {secretary_id} is not a secretary")
        raise ValueError("Provided assistant is not a secretary")

    # Deactivate existing active links for this user
    update_stmt = (
        UserSecretaryLink.__table__.update()
        .where(UserSecretaryLink.user_id == user_id)
        .where(UserSecretaryLink.is_active == True)
        .values(is_active=False)
    )
    await db.execute(update_stmt)
    # Note: Standard session commit below will commit this change too.

    # Check if this specific link already exists (and reactivate if inactive)
    existing_link_query = (
        select(UserSecretaryLink)
        .where(UserSecretaryLink.user_id == user_id)
        .where(UserSecretaryLink.secretary_id == secretary_id)
    )
    result = await db.execute(existing_link_query)
    existing_link = result.scalar_one_or_none()

    if existing_link:
        logger.info(
            f"Reactivating existing link for user {user_id} and secretary {secretary_id}"
        )
        existing_link.is_active = True
        db.add(existing_link)
        await db.commit()
        await db.refresh(existing_link)
        return existing_link
    else:
        # Create new active link
        logger.info(
            f"Creating new active link for user {user_id} and secretary {secretary_id}"
        )
        new_link = UserSecretaryLink(
            user_id=user_id, secretary_id=secretary_id, is_active=True
        )
        db.add(new_link)
        await db.commit()
        await db.refresh(new_link)
        return new_link


async def get_secretary_assignment(
    db: AsyncSession, user_id: int, secretary_id: UUID
) -> Optional[UserSecretaryLink]:
    """Get a specific assignment link between a user and a secretary."""
    query = (
        select(UserSecretaryLink)
        .where(UserSecretaryLink.user_id == user_id)
        .where(UserSecretaryLink.secretary_id == secretary_id)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def deactivate_secretary_assignment(
    db: AsyncSession, user_id: int, secretary_id: UUID
) -> bool:
    """Deactivate the link between a user and a secretary."""
    link = await get_secretary_assignment(db, user_id, secretary_id)
    if not link or not link.is_active:
        logger.warning(
            f"Active link not found to deactivate for user {user_id} and secretary {secretary_id}"
        )
        return False

    link.is_active = False
    db.add(link)
    await db.commit()
    logger.info(f"Deactivated link for user {user_id} and secretary {secretary_id}")
    return True
