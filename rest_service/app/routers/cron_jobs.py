from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import CronJob, CronJobType, CronJobStatus, TelegramUser
from app.database import get_session

router = APIRouter()

class CronJobCreate(BaseModel):
    name: str
    type: CronJobType
    cron_expression: str
    user_id: int

class CronJobUpdateRequest(BaseModel):
    name: Optional[str]
    type: Optional[CronJobType]
    cron_expression: Optional[str]

    def dict_for_update(self):
        """Возвращает словарь только с установленными полями."""
        return {key: value for key, value in self.model_dump(exclude_unset=True).items() if value is not None}


@router.get("/cronjobs/")
async def list_cronjobs(session: AsyncSession = Depends(get_session)):
    """Получить список всех CronJob."""
    query = select(CronJob)
    result = await session.execute(query)
    return result.scalars().all()

@router.get("/cronjobs/{cronjob_id}")
async def get_cronjob(cronjob_id: int, session: AsyncSession = Depends(get_session)):
    """Получить CronJob по ID."""
    cronjob = await session.get(CronJob, cronjob_id)
    if not cronjob:
        raise HTTPException(status_code=404, detail="CronJob not found")
    return cronjob

@router.post("/cronjobs/")
async def create_cronjob(cronjob_data: CronJobCreate, session: AsyncSession = Depends(get_session)):
    """Создать новый CronJob."""
    user = await session.get(TelegramUser, cronjob_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cronjob = CronJob(
        name=cronjob_data.name,
        type=cronjob_data.type,
        cron_expression=cronjob_data.cron_expression,
        user_id=cronjob_data.user_id,
    )

    session.add(cronjob)
    await session.commit()
    await session.refresh(cronjob)
    return cronjob

@router.patch("/cronjobs/{cronjob_id}")
async def update_cronjob(cronjob_id: int, update_data: CronJobUpdateRequest, session: AsyncSession = Depends(get_session)):
    """Обновить CronJob по ID."""
    cronjob = await session.get(CronJob, cronjob_id)
    if not cronjob:
        raise HTTPException(status_code=404, detail="CronJob not found")

    updates = update_data.dict_for_update()
    for key, value in updates.items():
        setattr(cronjob, key, value)

    session.add(cronjob)
    await session.commit()
    await session.refresh(cronjob)
    return cronjob

@router.delete("/cronjobs/{cronjob_id}")
async def delete_cronjob(cronjob_id: int, session: AsyncSession = Depends(get_session)):
    """Удалить CronJob по ID."""
    cronjob = await session.get(CronJob, cronjob_id)
    if not cronjob:
        raise HTTPException(status_code=404, detail="CronJob not found")

    await session.delete(cronjob)
    await session.commit()
    return {"message": f"CronJob with ID {cronjob_id} has been deleted"}
