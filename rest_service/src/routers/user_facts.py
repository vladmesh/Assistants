from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from shared_models.api_schemas.user_fact import UserFactCreate, UserFactRead
from sqlmodel.ext.asyncio.session import AsyncSession

import crud
from database import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter()


@router.post(
    "/users/{user_id}/facts",
    response_model=UserFactRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_fact_for_user(user_id: int, fact_in: UserFactCreate, db: SessionDep):
    """Create a new fact for a specific user."""
    # Optional: Check if user exists
    db_user = await crud.get_user(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Ensure the user_id in the path matches the one in the payload
    if fact_in.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User ID in path does not match User ID in payload",
        )

    db_fact = await crud.create_user_fact(db=db, user_fact_in=fact_in)
    return db_fact


@router.get("/users/{user_id}/facts", response_model=list[UserFactRead])
async def read_facts_for_user(user_id: int, db: SessionDep):
    """Retrieve all facts for a specific user."""
    # Optional: Check if user exists
    db_user = await crud.get_user(db=db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    facts = await crud.get_user_facts_by_user_id(db=db, user_id=user_id)
    return facts


@router.delete("/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact(fact_id: UUID, db: SessionDep):
    """Delete a specific fact by its ID."""
    db_fact = await crud.get_user_fact_by_id(db=db, fact_id=fact_id)
    if not db_fact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found"
        )

    await crud.delete_user_fact(db=db, db_user_fact=db_fact)
    return None  # FastAPI handles the 204 response
