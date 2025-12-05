from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from shared_models.api_schemas import AssistantRead, UserSecretaryLinkRead
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import crud.user_secretary as user_secretary_crud
from database import get_session
from models.assistant import Assistant
from models.user_secretary import UserSecretaryLink

# Shared models import
# from shared_models.api_models import UserSecretaryAssignment # Remove this import

logger = structlog.get_logger()
SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter()


@router.get("/secretaries/")
async def list_secretaries(session: SessionDep):
    """Получить список всех доступных секретарей"""
    query = select(Assistant).where(Assistant.is_secretary.is_(True))
    result = await session.execute(query)
    secretaries = result.scalars().all()
    return secretaries


@router.get("/users/{user_id}/secretary", response_model=AssistantRead | None)
async def get_active_secretary_for_user_route(
    user_id: int, session: SessionDep
) -> Assistant | None:
    """Get the currently active secretary for a user."""
    logger.info("Getting active secretary for user", user_id=user_id)
    secretary = await user_secretary_crud.get_active_secretary_for_user(
        db=session, user_id=user_id
    )
    if not secretary:
        logger.info("No active secretary found for user", user_id=user_id)
        # Return 404 might be better here if a secretary is expected
        return None
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
    user_id: int, secretary_id: UUID, session: SessionDep
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
    except ValueError as exc:
        logger.error(
            "Failed to assign secretary: Invalid input",
            user_id=user_id,
            secretary_id=str(secretary_id),
            error=str(exc),
        )
        detail = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if "not found" in detail:
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except Exception as exc:
        logger.exception(
            "Failed to assign secretary due to unexpected error",
            user_id=user_id,
            secretary_id=str(secretary_id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


@router.delete(
    "/users/{user_id}/secretary/{secretary_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def deactivate_secretary_assignment_route(
    user_id: int, secretary_id: UUID, session: SessionDep
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


@router.get("/user-secretaries/assignments", response_model=list[UserSecretaryLinkRead])
async def list_active_user_secretary_assignments(
    session: SessionDep,
) -> list[UserSecretaryLink]:
    """Получить список всех активных назначений секретарей пользователям."""
    query = select(UserSecretaryLink).where(UserSecretaryLink.is_active.is_(True))
    result = await session.execute(query)
    active_links = result.scalars().all()
    # FastAPI converts ORM models to UserSecretaryLinkRead via from_attributes=True.
    return active_links


# Optional: Endpoint to get all assignments (might be useful for admin)
@router.get("/secretary-assignments/", response_model=list[UserSecretaryLinkRead])
async def list_all_secretary_assignments(
    session: SessionDep,
    user_id: int | None = None,
    secretary_id: UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[UserSecretaryLink]:
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
    result = await session.execute(query)
    assignments = result.scalars().all()
    logger.info(f"Found {len(assignments)} assignments")
    return assignments
