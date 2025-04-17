from typing import List, Optional

import crud.user as user_crud
import structlog
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.user import TelegramUser  # Keep for response_model
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import (
    TelegramUserCreate,
    TelegramUserRead,
    TelegramUserUpdate,
)

logger = structlog.get_logger()
router = APIRouter()


@router.post(
    "/users/", response_model=TelegramUserRead, status_code=status.HTTP_201_CREATED
)
async def create_user_route(
    user_in: TelegramUserCreate, session: AsyncSession = Depends(get_session)
) -> TelegramUser:
    """Create a new user."""
    logger.info(
        "Attempting to create user",
        telegram_id=user_in.telegram_id,
        username=user_in.username,
    )
    try:
        user = await user_crud.create_user(db=session, user_in=user_in)
        logger.info(
            "User created successfully", user_id=user.id, telegram_id=user.telegram_id
        )
        return user
    except ValueError as e:  # Catch specific error for existing user
        logger.warning(
            "Failed to create user: already exists",
            telegram_id=user_in.telegram_id,
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create user due to unexpected error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users/by-telegram-id/", response_model=TelegramUserRead)
async def get_user_by_telegram_id_route(
    telegram_id: int, session: AsyncSession = Depends(get_session)
) -> TelegramUser:
    """Get a user by telegram_id."""
    logger.info("Getting user by telegram_id", telegram_id=telegram_id)
    user = await user_crud.get_user_by_telegram_id(db=session, telegram_id=telegram_id)
    if not user:
        logger.warning("User not found by telegram_id", telegram_id=telegram_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    logger.info("User found by telegram_id", user_id=user.id, telegram_id=telegram_id)
    return user


@router.get("/users/{user_id}", response_model=TelegramUserRead)
async def get_user_by_id_route(
    user_id: int, session: AsyncSession = Depends(get_session)
) -> TelegramUser:
    """Get a user by internal database ID."""
    logger.info("Getting user by internal ID", user_id=user_id)
    user = await user_crud.get_user_by_id(db=session, user_id=user_id)
    if not user:
        logger.warning("User not found by internal ID", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    logger.info(
        "User found by internal ID", user_id=user_id, telegram_id=user.telegram_id
    )
    return user


@router.get("/users/", response_model=List[TelegramUserRead])
async def list_users_route(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> List[TelegramUser]:
    """Get a list of all users."""
    logger.info("Listing users", skip=skip, limit=limit)
    users = await user_crud.get_users(db=session, skip=skip, limit=limit)
    logger.info(f"Found {len(users)} users")
    return users


@router.patch("/users/{user_id}", response_model=TelegramUserRead)
async def update_user_route(
    user_id: int,
    user_update: TelegramUserUpdate,
    session: AsyncSession = Depends(get_session),
) -> TelegramUser:
    """Update user details (e.g., timezone, preferred_name) by internal ID."""
    logger.info(
        "Attempting to update user",
        user_id=user_id,
        update_data=user_update.model_dump(exclude_unset=True),
    )
    updated_user = await user_crud.update_user(
        db=session, user_id=user_id, user_in=user_update
    )
    if not updated_user:
        logger.warning("User not found for update", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    logger.info("User updated successfully", user_id=user_id)
    return updated_user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_route(
    user_id: int, session: AsyncSession = Depends(get_session)
) -> None:
    """Delete a user by internal database ID."""
    logger.info("Attempting to delete user", user_id=user_id)
    deleted = await user_crud.delete_user(db=session, user_id=user_id)
    if not deleted:
        logger.warning("User not found for deletion", user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    logger.info("User deleted successfully", user_id=user_id)
    return None  # Return None for 204 No Content
