from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

# Import Pydantic schemas from shared_models
from shared_models.api_schemas.user_summary import (
    UserSummaryCreateUpdate,
    UserSummaryRead,
)
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем все необходимые CRUD-модули
from crud import assistant as assistant_crud
from crud import user as user_crud
from crud import user_summary as user_summary_crud
from database import get_session
from models.user_summary import UserSummary

SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(
    tags=["User Summaries"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/user-summaries/",
    response_model=UserSummaryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Summary",
    description="Create a new summary.",
)
async def create_summary_endpoint(
    summary_in: UserSummaryCreateUpdate,
    db: SessionDep,
) -> UserSummary:
    user = await user_crud.get_user_by_id(db, user_id=summary_in.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {summary_in.user_id} not found",
        )
    assistant = await assistant_crud.get_assistant(
        db, assistant_id=summary_in.assistant_id
    )
    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assistant with id {summary_in.assistant_id} not found",
        )

    db_summary = await user_summary_crud.create_summary(db=db, obj_in=summary_in)
    return db_summary


@router.get("/user-summaries/", response_model=list[UserSummaryRead])
async def list_summaries_endpoint(
    db: SessionDep,
    user_id: Annotated[int | None, Query()] = None,
    assistant_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(le=1000)] = 100,
    offset: Annotated[int, Query()] = 0,
) -> list[UserSummary]:
    summaries = await user_summary_crud.get_multi_summaries(
        db=db, user_id=user_id, assistant_id=assistant_id, skip=offset, limit=limit
    )
    return summaries


@router.get(
    "/user-summaries/latest/",
    response_model=UserSummaryRead | None,
    summary="Get Latest User Summary",
    description="Retrieve the *latest* summary for a specific user and assistant.",
)
async def read_latest_summary_endpoint(
    db: SessionDep,
    user_id: Annotated[int, Query(...)],
    assistant_id: Annotated[UUID, Query(...)],
) -> UserSummary | None:
    db_summary = await user_summary_crud.get_latest_by_user_and_assistant(
        db=db, user_id=user_id, assistant_id=assistant_id
    )
    return db_summary


@router.get("/user-summaries/{summary_id}", response_model=UserSummaryRead)
async def get_summary_endpoint(summary_id: int, db: SessionDep) -> UserSummary:
    db_summary = await user_summary_crud.get_summary_by_id(db=db, id=summary_id)
    if not db_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found"
        )
    return db_summary


@router.patch("/user-summaries/{summary_id}", response_model=UserSummaryRead)
async def update_summary_endpoint(
    summary_id: int,
    summary_in: UserSummaryCreateUpdate,
    db: SessionDep,
) -> UserSummary:
    db_summary_to_update = await user_summary_crud.get_summary_by_id(
        db=db, id=summary_id
    )
    if not db_summary_to_update:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found"
        )

    update_data = summary_in.model_dump(exclude_unset=True)
    if (
        "user_id" in update_data
        and update_data["user_id"] != db_summary_to_update.user_id
    ):
        raise HTTPException(
            status_code=400, detail="Cannot change user_id of a summary via PATCH"
        )
    update_data.pop("user_id", None)

    if (
        "assistant_id" in update_data
        and update_data["assistant_id"] != db_summary_to_update.assistant_id
    ):
        raise HTTPException(
            status_code=400, detail="Cannot change assistant_id of a summary via PATCH"
        )
    update_data.pop("assistant_id", None)

    updated_summary = await user_summary_crud.update_summary(
        db=db, db_obj=db_summary_to_update, obj_in=update_data
    )
    return updated_summary


@router.delete(
    "/user-summaries/{summary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete User Summary",
    description="Delete an existing summary.",
)
async def delete_summary_endpoint(
    summary_id: int,
    db: SessionDep,
) -> None:
    db_summary = await user_summary_crud.get_summary_by_id(db, id=summary_id)
    if not db_summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary with id {summary_id} not found",
        )

    await user_summary_crud.delete_summary(db=db, id=summary_id)
