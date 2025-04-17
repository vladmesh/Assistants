from typing import List, Optional
from uuid import UUID

import crud.user_secretary as user_secretary_crud
import structlog
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from models.assistant import Assistant
from models.user_secretary import UserSecretaryLink
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared_models.api_schemas import AssistantRead, UserSecretaryLinkRead

# Shared models import
# from shared_models.api_models import UserSecretaryAssignment # Remove this import

logger = structlog.get_logger()
router = APIRouter()


@router.get("/secretaries/")
async def list_secretaries(session: AsyncSession = Depends(get_session)):
    """Получить список всех доступных секретарей"""
    query = select(Assistant).where(Assistant.is_secretary.is_(True))
    secretaries = (await session.exec(query)).all()
    return secretaries


@router.get("/users/{user_id}/secretary", response_model=Optional[AssistantRead])
async def get_active_secretary_for_user_route(
    user_id: int, session: AsyncSession = Depends(get_session)
) -> Optional[Assistant]:
    """Get the currently active secretary for a user."""
    logger.info("Getting active secretary for user", user_id=user_id)
    secretary = await user_secretary_crud.get_active_secretary_for_user(
        db=session, user_id=user_id
    )
    if not secretary:
        logger.info("No active secretary found for user", user_id=user_id)
        # Return 404 might be better here if a secretary is expected
        return None  # Or raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active secretary not found")
    logger.info(
        "Active secretary found", user_id=user_id, secretary_id=str(secretary.id)
    )
    return secretary


@router.post(
    "/users/{user_id}/secretary/{secretary_id}",
    response_model=UserSecretaryLinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_secretary_to_user_route(
    user_id: int, secretary_id: UUID, session: AsyncSession = Depends(get_session)
) -> UserSecretaryLink:
    """Assign a secretary to a user. This deactivates any previous assignments."""
    logger.info(
        "Assigning secretary to user", user_id=user_id, secretary_id=str(secretary_id)
    )
    try:
        link = await user_secretary_crud.assign_secretary_to_user(
            db=session, user_id=user_id, secretary_id=secretary_id
        )
        logger.info(
            "Secretary assigned successfully",
            user_id=user_id,
            secretary_id=str(secretary_id),
            link_id=str(link.id),
        )
        return link
    except ValueError as e:
        logger.error(
            "Failed to assign secretary: Invalid input",
            user_id=user_id,
            secretary_id=str(secretary_id),
            error=str(e),
        )
        detail = str(e)
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail)
    except Exception as e:
        logger.exception(
            "Failed to assign secretary due to unexpected error",
            user_id=user_id,
            secretary_id=str(secretary_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/users/{user_id}/secretary/{secretary_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def deactivate_secretary_assignment_route(
    user_id: int, secretary_id: UUID, session: AsyncSession = Depends(get_session)
) -> None:
    """Deactivate the assignment between a user and a secretary."""
    logger.info(
        "Deactivating secretary assignment",
        user_id=user_id,
        secretary_id=str(secretary_id),
    )
    deactivated = await user_secretary_crud.deactivate_secretary_assignment(
        db=session, user_id=user_id, secretary_id=secretary_id
    )
    if not deactivated:
        logger.warning(
            "Active secretary assignment not found for deactivation",
            user_id=user_id,
            secretary_id=str(secretary_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Active assignment not found"
        )
    logger.info(
        "Secretary assignment deactivated successfully",
        user_id=user_id,
        secretary_id=str(secretary_id),
    )
    return None  # Return None for 204 No Content


@router.get("/user-secretaries/assignments", response_model=List[UserSecretaryLinkRead])
async def list_active_user_secretary_assignments(
    session: AsyncSession = Depends(get_session),
) -> List[UserSecretaryLink]:
    """Получить список всех активных назначений секретарей пользователям."""
    query = select(UserSecretaryLink).where(UserSecretaryLink.is_active.is_(True))
    active_links = (await session.exec(query)).all()
    # FastAPI will automatically convert these ORM models to the UserSecretaryLinkRead response model
    # because of from_attributes=True in the schema's config
    return active_links


# Optional: Endpoint to get all assignments (might be useful for admin)
@router.get("/secretary-assignments/", response_model=List[UserSecretaryLinkRead])
async def list_all_secretary_assignments(
    session: AsyncSession = Depends(get_session),
    user_id: Optional[int] = None,
    secretary_id: Optional[UUID] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[UserSecretaryLink]:
    """List all user-secretary assignments, with optional filters."""
    logger.info(
        "Listing secretary assignments",
        user_id=user_id,
        secretary_id=str(secretary_id) if secretary_id else None,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    query = select(UserSecretaryLink)
    if user_id is not None:
        query = query.where(UserSecretaryLink.user_id == user_id)
    if secretary_id is not None:
        query = query.where(UserSecretaryLink.secretary_id == secretary_id)
    if is_active is not None:
        query = query.where(UserSecretaryLink.is_active == is_active)

    query = query.offset(skip).limit(limit)
    assignments = (await session.exec(query)).all()
    logger.info(f"Found {len(assignments)} assignments")
    return assignments
