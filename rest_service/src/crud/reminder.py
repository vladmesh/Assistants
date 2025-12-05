import json  # Import json
import logging
from datetime import UTC
from uuid import UUID

from shared_models.api_schemas import ReminderCreate
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.reminder import Reminder, ReminderStatus, ReminderType
from models.user import TelegramUser  # To check user existence

logger = logging.getLogger(__name__)


async def get_reminder(db: AsyncSession, reminder_id: UUID) -> Reminder | None:
    """Get a reminder by its ID."""
    reminder = await db.get(Reminder, reminder_id)
    return reminder


async def get_reminders(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[Reminder]:
    """Get a list of all reminders with pagination."""
    query = select(Reminder).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def get_scheduled_reminders(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[Reminder]:
    """Get a list of active reminders for the scheduler."""
    query = (
        select(Reminder)
        .where(Reminder.status == ReminderStatus.ACTIVE)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def get_user_reminders(
    db: AsyncSession,
    user_id: int,
    status: ReminderStatus | None = None,
    type: ReminderType | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Reminder]:
    """Get a list of reminders for a specific user with optional filters."""
    # Check if user exists first
    user = await db.get(TelegramUser, user_id)
    if not user:
        logger.warning(f"Attempted to get reminders for non-existent user: {user_id}")
        # Return empty list or raise error based on requirements
        return []

    query = select(Reminder).where(Reminder.user_id == user_id)
    if status:
        query = query.where(Reminder.status == status)
    if type:
        query = query.where(Reminder.type == type)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def create_reminder(db: AsyncSession, reminder_in: ReminderCreate) -> Reminder:
    """Create a new reminder."""
    # Check user exists
    user = await db.get(TelegramUser, reminder_in.user_id)
    if not user:
        logger.error(f"User not found when creating reminder: {reminder_in.user_id}")
        raise ValueError("User not found")

    # Handle timezone-aware datetime conversion to naive UTC
    trigger_at_naive_utc = None
    if reminder_in.trigger_at:
        if reminder_in.trigger_at.tzinfo is not None:
            trigger_at_naive_utc = reminder_in.trigger_at.astimezone(UTC).replace(
                tzinfo=None
            )
        else:
            # Assume naive datetime is already in UTC (or adjust logic if needed)
            trigger_at_naive_utc = reminder_in.trigger_at

    # Validate enums before creating the model instance
    try:
        reminder_type = ReminderType(reminder_in.type)
        reminder_status = ReminderStatus(reminder_in.status)
    except ValueError as exc:
        logger.error(f"Invalid enum value provided for reminder: {exc}")
        raise ValueError(f"Invalid reminder type or status: {exc}") from exc

    # Convert payload dict to JSON string before creating model
    payload_str = json.dumps(reminder_in.payload, ensure_ascii=False)

    # Create Reminder instance using validated data
    db_reminder = Reminder(
        user_id=reminder_in.user_id,
        assistant_id=reminder_in.assistant_id,
        type=reminder_type,
        trigger_at=trigger_at_naive_utc,
        cron_expression=reminder_in.cron_expression,
        payload=payload_str,  # Use the JSON string
        status=reminder_status,
    )

    db.add(db_reminder)
    await db.commit()
    await db.refresh(db_reminder)
    logger.info(
        f"Reminder created with ID: {db_reminder.id} for user {db_reminder.user_id}"
    )
    return db_reminder


async def update_reminder_status(
    db: AsyncSession, reminder_id: UUID, status: ReminderStatus
) -> Reminder | None:
    """Update the status of a specific reminder."""
    db_reminder = await get_reminder(db, reminder_id)
    if not db_reminder:
        logger.warning(f"Reminder not found for status update: {reminder_id}")
        return None

    db_reminder.status = status
    db.add(db_reminder)
    await db.commit()
    await db.refresh(db_reminder)
    logger.info(f"Reminder status updated to {status} for ID: {reminder_id}")
    return db_reminder


async def delete_reminder(db: AsyncSession, reminder_id: UUID) -> bool:
    """Delete a reminder by its ID."""
    db_reminder = await get_reminder(db, reminder_id)
    if not db_reminder:
        logger.warning(f"Reminder not found for deletion: {reminder_id}")
        return False

    await db.delete(db_reminder)
    await db.commit()
    logger.info(f"Reminder deleted with ID: {reminder_id}")
    return True
