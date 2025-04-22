from typing import Optional
from uuid import UUID

# Импортируем все необходимые CRUD-модули
from crud import assistant as assistant_crud
from crud import user as user_crud
from crud import user_summary as user_summary_crud
from database import get_session
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# Import Pydantic schemas from shared_models
from shared_models.api_schemas.user_summary import (
    UserSummaryCreateUpdate,
    UserSummaryRead,
)

router = APIRouter(
    prefix="/user-summaries",
    tags=["User Summaries"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/{user_id}/{secretary_id}/latest",
    response_model=Optional[UserSummaryRead],
    summary="Get Latest User Summary",
    description="Retrieve the *latest* summary for a specific user and secretary.",
)
async def read_latest_user_summary(
    user_id: int,
    secretary_id: UUID,
    db: AsyncSession = Depends(get_session),
):
    """Retrieve the summary associated with a specific user ID and secretary ID."""
    db_summary = await user_summary_crud.get_summary(
        db=db, user_id=user_id, secretary_id=secretary_id
    )
    if db_summary is None:
        # Return 200 OK with null body if not found, as per response_model=Optional[...]
        return None
    return db_summary


@router.post(
    "/{user_id}/{secretary_id}",
    response_model=UserSummaryRead,
    status_code=status.HTTP_200_OK,  # Return 200 for update, 201 usually for pure creation
    summary="Create or Update User Summary",
    description="Create a new summary or update the existing one for a user and secretary.",
)
async def create_or_update_user_summary(
    user_id: int,
    secretary_id: UUID,
    summary_in: UserSummaryCreateUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Create a new user summary entry (does not update anymore)."""
    # Проверяем существование пользователя
    user = await user_crud.get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found",
        )
    # Проверяем существование секретаря
    secretary = await assistant_crud.get_assistant(db, assistant_id=secretary_id)
    if not secretary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secretary with id {secretary_id} not found",
        )
    if not secretary.is_secretary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Assistant {secretary_id} is not a secretary",
        )

    db_summary = await user_summary_crud.create_or_update_summary(
        db=db,
        user_id=user_id,
        secretary_id=secretary_id,
        summary_text=summary_in.summary_text,
    )
    return db_summary
