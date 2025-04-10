from typing import List
from uuid import UUID

from database import get_session
from fastapi import APIRouter, Depends, HTTPException
from models.assistant import Assistant
from models.user_secretary import UserSecretaryLink
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

# Shared models import
from shared_models.api_models import UserSecretaryAssignment

router = APIRouter()


@router.get("/secretaries/")
async def list_secretaries(session: AsyncSession = Depends(get_session)):
    """Получить список всех доступных секретарей"""
    query = select(Assistant).where(Assistant.is_secretary.is_(True))
    result = await session.execute(query)
    secretaries = result.scalars().all()
    return secretaries


@router.get("/users/{user_id}/secretary")
async def get_user_secretary(
    user_id: int, session: AsyncSession = Depends(get_session)
):
    """Получить текущего секретаря пользователя"""
    query = select(UserSecretaryLink).where(
        UserSecretaryLink.user_id == user_id, UserSecretaryLink.is_active.is_(True)
    )
    result = await session.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=404, detail="No active secretary found for user"
        )

    # Загружаем данные секретаря
    await session.refresh(link, ["secretary"])
    return link.secretary


@router.post("/users/{user_id}/secretary/{secretary_id}")
async def set_user_secretary(
    user_id: int, secretary_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Установить секретаря для пользователя"""
    # Проверяем существование секретаря
    secretary = await session.get(Assistant, secretary_id)
    if not secretary or not secretary.is_secretary:
        raise HTTPException(status_code=404, detail="Secretary not found")

    # Деактивируем предыдущие связи
    query = select(UserSecretaryLink).where(
        UserSecretaryLink.user_id == user_id, UserSecretaryLink.is_active.is_(True)
    )
    result = await session.execute(query)
    old_links = result.scalars().all()

    for link in old_links:
        link.is_active = False

    # Создаем новую связь
    new_link = UserSecretaryLink(
        user_id=user_id, secretary_id=secretary_id, is_active=True
    )
    session.add(new_link)
    await session.commit()
    await session.refresh(new_link)

    return new_link


@router.get(
    "/user-secretaries/assignments", response_model=List[UserSecretaryAssignment]
)
async def list_active_user_secretary_assignments(
    session: AsyncSession = Depends(get_session),
):
    """Получить список всех активных назначений секретарей пользователям."""
    query = select(UserSecretaryLink).where(UserSecretaryLink.is_active.is_(True))
    result = await session.execute(query)
    active_links = result.scalars().all()
    # Map to the response model
    return [
        UserSecretaryAssignment(
            user_id=link.user_id,
            secretary_id=link.secretary_id,
            updated_at=link.updated_at,  # Assuming updated_at exists on UserSecretaryLink
        )
        for link in active_links
    ]
