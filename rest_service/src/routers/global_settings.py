from typing import Annotated

from fastapi import APIRouter, Depends
from shared_models.api_schemas import GlobalSettingsRead, GlobalSettingsUpdate
from sqlalchemy.ext.asyncio import AsyncSession

import crud.global_settings as global_settings_crud
from database import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
router = APIRouter(
    prefix="/global-settings",
    tags=["Global Settings"],
)


@router.get("/", response_model=GlobalSettingsRead)
async def read_global_settings(db: SessionDep):
    """Retrieve the global system settings.

    If settings do not exist, they will be created with default values.
    """
    settings = await global_settings_crud.get_global_settings(db)
    if settings is None:
        # Settings not found, create them with defaults
        settings = await global_settings_crud.create_default_global_settings(db)
    return settings


@router.put("/", response_model=GlobalSettingsRead)
async def update_global_settings(settings_in: GlobalSettingsUpdate, db: SessionDep):
    """Update the global system settings.

    Creates the settings record if it doesn't exist.
    """
    updated_settings = await global_settings_crud.upsert_global_settings(
        db=db, settings_in=settings_in
    )
    return updated_settings
