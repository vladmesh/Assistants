from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID
from datetime import datetime, UTC

from models.assistant import UserAssistantThread
from database import get_session

router = APIRouter()


@router.get("/users/{user_id}/assistants/{assistant_id}/thread")
async def get_user_assistant_thread(
    user_id: str, assistant_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Получить thread_id для пары пользователь-ассистент"""
    query = select(UserAssistantThread).where(
        UserAssistantThread.user_id == user_id,
        UserAssistantThread.assistant_id == assistant_id,
    )
    result = await session.execute(query)
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    return thread


@router.post("/users/{user_id}/assistants/{assistant_id}/thread")
async def create_user_assistant_thread(
    user_id: str,
    assistant_id: UUID,
    thread_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Создать или обновить thread_id для пары пользователь-ассистент"""
    # Проверяем существование треда
    query = select(UserAssistantThread).where(
        UserAssistantThread.user_id == user_id,
        UserAssistantThread.assistant_id == assistant_id,
    )
    result = await session.execute(query)
    existing_thread = result.scalar_one_or_none()

    if existing_thread:
        # Обновляем существующий тред
        existing_thread.thread_id = thread_id
        existing_thread.last_used = datetime.now(UTC)
        await session.commit()
        await session.refresh(existing_thread)
        return existing_thread

    # Создаем новый тред
    new_thread = UserAssistantThread(
        user_id=user_id, assistant_id=assistant_id, thread_id=thread_id
    )
    session.add(new_thread)
    await session.commit()
    await session.refresh(new_thread)

    return new_thread
