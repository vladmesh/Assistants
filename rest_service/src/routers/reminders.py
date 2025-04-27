from typing import List, Optional
from uuid import UUID

import crud.reminder as reminder_crud
import structlog
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.reminder import Reminder, ReminderStatus, ReminderType
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import ReminderCreate, ReminderRead, ReminderUpdate

logger = structlog.get_logger()
router = APIRouter()


@router.get("/reminders/", response_model=List[ReminderRead])
async def list_reminders_route(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> List[Reminder]:
    """Get a list of all reminders with pagination."""
    logger.info("Listing reminders", skip=skip, limit=limit)
    reminders = await reminder_crud.get_reminders(db=session, skip=skip, limit=limit)
    logger.info(f"Found {len(reminders)} reminders")
    return reminders


@router.get("/reminders/scheduled", response_model=List[ReminderRead])
async def list_scheduled_reminders_route(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> List[Reminder]:
    """Get a list of active reminders for the scheduler."""
    logger.info("Listing scheduled (active) reminders", skip=skip, limit=limit)
    reminders = await reminder_crud.get_scheduled_reminders(
        db=session, skip=skip, limit=limit
    )
    logger.info(f"Found {len(reminders)} scheduled reminders")
    return reminders


@router.get("/reminders/{reminder_id}", response_model=ReminderRead)
async def get_reminder_route(
    reminder_id: UUID, session: AsyncSession = Depends(get_session)
) -> Reminder:
    """Get a reminder by ID."""
    logger.info("Getting reminder by ID", reminder_id=str(reminder_id))
    reminder = await reminder_crud.get_reminder(db=session, reminder_id=reminder_id)
    if not reminder:
        logger.warning("Reminder not found", reminder_id=str(reminder_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found"
        )
    logger.info("Reminder found", reminder_id=str(reminder_id))
    return reminder


@router.get("/reminders/user/{user_id}", response_model=List[ReminderRead])
async def list_user_reminders_route(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status (active, completed, cancelled)",
    ),
    type_filter: Optional[str] = Query(
        None, alias="type", description="Filter by type (one_time, recurring)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> List[Reminder]:
    """Get a list of reminders for a user with filtering and pagination."""
    logger.info(
        "Listing user reminders",
        user_id=user_id,
        status=status_filter,
        type=type_filter,
        skip=skip,
        limit=limit,
    )

    # Validate status and type filters against enums
    status_enum: Optional[ReminderStatus] = None
    if status_filter:
        try:
            status_enum = ReminderStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter value: {status_filter}",
            )

    type_enum: Optional[ReminderType] = None
    if type_filter:
        try:
            type_enum = ReminderType(type_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type filter value: {type_filter}",
            )

    reminders = await reminder_crud.get_user_reminders(
        db=session,
        user_id=user_id,
        status=status_enum,
        type=type_enum,
        skip=skip,
        limit=limit,
    )
    logger.info(f"Found {len(reminders)} reminders for user", user_id=user_id)
    return reminders


@router.post(
    "/reminders/", response_model=ReminderRead, status_code=status.HTTP_201_CREATED
)
async def create_reminder_route(
    reminder_data: ReminderCreate, session: AsyncSession = Depends(get_session)
) -> Reminder:
    """Create a new reminder."""
    logger.info(
        "Attempting to create reminder",
        user_id=reminder_data.user_id,
        type=reminder_data.type,
    )
    try:
        reminder = await reminder_crud.create_reminder(
            db=session, reminder_in=reminder_data
        )
        logger.info(
            "Reminder created successfully",
            reminder_id=str(reminder.id),
            user_id=reminder.user_id,
        )
        return reminder
    except ValueError as e:
        logger.error(
            "Failed to create reminder: Invalid input",
            error=str(e),
            user_id=reminder_data.user_id,
        )
        # Check if it's a user not found error or enum error
        detail = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        if "User not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception:
        logger.exception(
            "Failed to create reminder due to unexpected error",
            user_id=reminder_data.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.patch("/reminders/{reminder_id}", response_model=ReminderRead)
async def update_reminder_status_route(
    reminder_id: UUID,
    update_data: ReminderUpdate,  # Pydantic model for partial updates
    session: AsyncSession = Depends(get_session),
) -> Reminder:
    """Update the status of a reminder."""
    logger.info(
        "Attempting to update reminder status",
        reminder_id=str(reminder_id),
        new_status=update_data.status,
    )
    if update_data.status is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status field is required for update",
        )

    # Validate status enum
    try:
        status_enum = ReminderStatus(update_data.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status value: {update_data.status}",
        )

    updated_reminder = await reminder_crud.update_reminder_status(
        db=session, reminder_id=reminder_id, status=status_enum
    )
    if not updated_reminder:
        logger.warning(
            "Reminder not found for status update", reminder_id=str(reminder_id)
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found"
        )

    logger.info(
        "Reminder status updated successfully",
        reminder_id=str(reminder_id),
        status=updated_reminder.status,
    )
    return updated_reminder


@router.delete("/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder_route(
    reminder_id: UUID, session: AsyncSession = Depends(get_session)
) -> None:
    """Delete a reminder."""
    logger.info("Attempting to delete reminder", reminder_id=str(reminder_id))
    deleted = await reminder_crud.delete_reminder(db=session, reminder_id=reminder_id)
    if not deleted:
        logger.warning("Reminder not found for deletion", reminder_id=str(reminder_id))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found"
        )
    logger.info("Reminder deleted successfully", reminder_id=str(reminder_id))
    return None
