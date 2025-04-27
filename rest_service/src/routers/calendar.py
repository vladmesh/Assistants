from typing import Optional

import crud.calendar as calendar_crud
import structlog
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from models.calendar import CalendarCredentials
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import CalendarCredentialsCreate, CalendarCredentialsRead

logger = structlog.get_logger()
router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.put(
    "/user/{user_id}/token",
    response_model=CalendarCredentialsRead,
    status_code=status.HTTP_200_OK,
)
async def update_calendar_token_route(
    user_id: int,
    creds_in: CalendarCredentialsCreate,
    db: AsyncSession = Depends(get_session),
) -> CalendarCredentials:
    """Update or create user's Google Calendar token"""
    logger.info("Attempting to update/create calendar token", user_id=user_id)
    try:
        credentials = await calendar_crud.create_or_update_credentials(
            db=db, user_id=user_id, creds_in=creds_in
        )
        logger.info("Calendar token updated/created successfully", user_id=user_id)
        return credentials
    except ValueError as e:
        logger.error(
            "Failed update/create calendar token: User not found",
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    except Exception:
        logger.exception(
            "Failed to update/create calendar token due to unexpected error",
            user_id=user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update token",
        )


@router.get("/user/{user_id}/token", response_model=Optional[CalendarCredentialsRead])
async def get_calendar_token_route(
    user_id: int, db: AsyncSession = Depends(get_session)
) -> Optional[CalendarCredentials]:
    """Get user's Google Calendar token"""
    logger.info("Attempting to get calendar token", user_id=user_id)
    try:
        credentials = await calendar_crud.get_credentials(db=db, user_id=user_id)
        if not credentials:
            logger.info("No calendar token found for user", user_id=user_id)
            return None
        logger.info("Calendar token retrieved successfully", user_id=user_id)
        return credentials
    except Exception:
        logger.exception(
            "Failed to get calendar token due to unexpected error", user_id=user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get token",
        )


@router.delete("/user/{user_id}/token", status_code=status.HTTP_204_NO_CONTENT)
async def delete_calendar_token_route(
    user_id: int, db: AsyncSession = Depends(get_session)
) -> None:
    """Delete user's Google Calendar token"""
    logger.info("Attempting to delete calendar token", user_id=user_id)
    try:
        deleted = await calendar_crud.delete_credentials(db=db, user_id=user_id)
        if not deleted:
            logger.warning("Calendar token not found for deletion", user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Credentials not found"
            )
        logger.info("Calendar token deleted successfully", user_id=user_id)
        return None
    except Exception:
        logger.exception(
            "Failed to delete calendar token due to unexpected error", user_id=user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete token",
        )
