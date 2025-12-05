import datetime

from shared_models.api_schemas import GlobalSettingsUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models import GlobalSettings


async def get_global_settings(db: AsyncSession) -> GlobalSettings | None:
    """Fetches the single global settings record (id=1)."""
    result = await db.execute(select(GlobalSettings).where(GlobalSettings.id == 1))
    return result.scalars().first()


async def create_default_global_settings(db: AsyncSession) -> GlobalSettings:
    """Creates the default global settings record (id=1)."""
    # Create with default values defined in the model
    default_settings = GlobalSettings(id=1)
    db.add(default_settings)
    await db.commit()
    await db.refresh(default_settings)
    return default_settings


async def upsert_global_settings(
    db: AsyncSession, settings_in: GlobalSettingsUpdate
) -> GlobalSettings:
    """Updates the global settings record (id=1) or creates it if it doesn't exist."""
    db_settings = await get_global_settings(db)

    if db_settings:
        # Update existing settings
        update_data = settings_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_settings, key, value)
        # Manually update timestamp
        db_settings.updated_at = datetime.datetime.now(datetime.UTC)
        await db.commit()
        await db.refresh(db_settings)
        return db_settings
    else:
        # Create new settings using provided data and model defaults
        # Start with model defaults
        new_settings = GlobalSettings(id=1)
        # Override with provided non-None values
        update_data = settings_in.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(new_settings, key, value)

        db.add(new_settings)
        await db.commit()
        await db.refresh(new_settings)
        return new_settings
