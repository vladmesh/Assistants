from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from database import get_session
from fastapi import APIRouter, Depends, HTTPException, Query
from models import Reminder, TelegramUser
from schemas import ReminderCreate, ReminderRead, ReminderUpdate
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter()


@router.get("/reminders/", response_model=List[ReminderRead])
async def list_reminders(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Получить список всех напоминаний с пагинацией."""
    query = select(Reminder).offset(skip).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/reminders/scheduled", response_model=List[ReminderRead])
async def list_scheduled_reminders(
    session: AsyncSession = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Получить список активных напоминаний для планировщика."""
    query = (
        select(Reminder).where(Reminder.status == "active").offset(skip).limit(limit)
    )
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/reminders/{reminder_id}", response_model=ReminderRead)
async def get_reminder(reminder_id: UUID, session: AsyncSession = Depends(get_session)):
    """Получить напоминание по ID."""
    reminder = await session.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")
    return reminder


@router.get("/reminders/user/{user_id}", response_model=List[ReminderRead])
async def list_user_reminders(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    status: Optional[str] = None,
    type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Получить список напоминаний пользователя с фильтрацией и пагинацией."""
    # Проверяем существование пользователя
    user = await session.get(TelegramUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Формируем базовый запрос
    query = select(Reminder).where(Reminder.user_id == user_id)

    # Добавляем фильтры, если они указаны
    if status:
        query = query.where(Reminder.status == status)
    if type:
        query = query.where(Reminder.type == type)

    # Добавляем пагинацию
    query = query.offset(skip).limit(limit)

    # Выполняем запрос
    result = await session.execute(query)
    return result.scalars().all()


@router.post("/reminders/", response_model=ReminderRead, status_code=201)
async def create_reminder(
    reminder_data: ReminderCreate, session: AsyncSession = Depends(get_session)
):
    """Создать новое напоминание."""
    # Проверяем существование пользователя
    user = await session.get(TelegramUser, reminder_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Преобразуем trigger_at в naive UTC, если он aware
    trigger_at_naive_utc = None
    if reminder_data.trigger_at:
        if reminder_data.trigger_at.tzinfo is not None:
            # Если datetime aware, конвертируем в UTC и делаем naive
            trigger_at_naive_utc = reminder_data.trigger_at.astimezone(
                timezone.utc
            ).replace(tzinfo=None)
        else:
            # Если datetime уже naive, предполагаем, что это UTC (или нужно уточнить логику)
            trigger_at_naive_utc = reminder_data.trigger_at

    # Создаем напоминание с преобразованным временем
    reminder = Reminder(
        user_id=reminder_data.user_id,
        assistant_id=reminder_data.assistant_id,
        created_by_assistant_id=reminder_data.assistant_id,
        type=reminder_data.type,
        trigger_at=trigger_at_naive_utc,  # Используем преобразованное время
        cron_expression=reminder_data.cron_expression,
        payload=reminder_data.payload,
        status=reminder_data.status,
    )

    # Сохраняем в базу данных
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)

    return reminder


@router.patch("/reminders/{reminder_id}", response_model=ReminderRead)
async def update_reminder(
    reminder_id: UUID,
    update_data: ReminderUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Обновить статус напоминания."""
    # Получаем напоминание
    reminder = await session.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")

    # Обновляем статус
    if update_data.status is not None:
        reminder.status = update_data.status

    # Сохраняем изменения
    await session.commit()
    await session.refresh(reminder)

    return reminder


@router.delete("/reminders/{reminder_id}", status_code=204)
async def delete_reminder(
    reminder_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Удалить напоминание."""
    # Получаем напоминание
    reminder = await session.get(Reminder, reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="Напоминание не найдено")

    # Удаляем напоминание
    await session.delete(reminder)
    await session.commit()

    return None
