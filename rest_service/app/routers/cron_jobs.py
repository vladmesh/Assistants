from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
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
def list_cronjobs(session: Session = Depends(get_session)):
    """Получить список всех CronJob."""
    query = select(CronJob)
    return session.exec(query).all()

@router.get("/cronjobs/{cronjob_id}")
def get_cronjob(cronjob_id: int, session: Session = Depends(get_session)):
    """Получить CronJob по ID."""
    cronjob = session.get(CronJob, cronjob_id)
    if not cronjob:
        raise HTTPException(status_code=404, detail="CronJob not found")
    return cronjob

@router.post("/cronjobs/")
def create_cronjob(cronjob_data: CronJobCreate, session: Session = Depends(get_session)):
    """Создать новый CronJob."""
    user = session.get(TelegramUser, cronjob_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    cronjob = CronJob(
        name=cronjob_data.name,
        type=cronjob_data.type,
        cron_expression=cronjob_data.cron_expression,
        user_id=cronjob_data.user_id,
    )

    session.add(cronjob)
    session.commit()
    session.refresh(cronjob)
    return cronjob

@router.patch("/cronjobs/{cronjob_id}")
def update_cronjob(cronjob_id: int, update_data: CronJobUpdateRequest, session: Session = Depends(get_session)):
    """Обновить CronJob по ID."""
    cronjob = session.get(CronJob, cronjob_id)
    if not cronjob:
        raise HTTPException(status_code=404, detail="CronJob not found")

    updates = update_data.dict_for_update()
    for key, value in updates.items():
        setattr(cronjob, key, value)

    session.add(cronjob)
    session.commit()
    session.refresh(cronjob)
    return cronjob

@router.delete("/cronjobs/{cronjob_id}")
def delete_cronjob(cronjob_id: int, session: Session = Depends(get_session)):
    """Удалить CronJob по ID."""
    cronjob = session.get(CronJob, cronjob_id)
    if not cronjob:
        raise HTTPException(status_code=404, detail="CronJob not found")

    session.delete(cronjob)
    session.commit()
    return {"message": f"CronJob with ID {cronjob_id} has been deleted"}
