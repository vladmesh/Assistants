from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID

from models.assistant import Assistant, Tool, AssistantToolLink
from database import get_session

router = APIRouter()


@router.post("/assistants/{assistant_id}/tools/{tool_id}")
async def add_tool_to_assistant(
    assistant_id: UUID, tool_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Добавить инструмент к ассистенту"""
    # Проверяем существование ассистента
    assistant = await session.get(Assistant, assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")

    # Проверяем существование инструмента
    tool = await session.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    # Проверяем, не существует ли уже такая связь
    query = select(AssistantToolLink).where(
        AssistantToolLink.assistant_id == assistant_id,
        AssistantToolLink.tool_id == tool_id,
        AssistantToolLink.is_active == True,
    )
    result = await session.execute(query)
    existing_link = result.scalar_one_or_none()

    if existing_link:
        raise HTTPException(
            status_code=400, detail="Tool is already linked to this assistant"
        )

    # Создаем новую связь
    link = AssistantToolLink(assistant_id=assistant_id, tool_id=tool_id)
    session.add(link)
    await session.commit()
    await session.refresh(link)

    return {"message": "Tool successfully linked to assistant"}


@router.delete("/assistants/{assistant_id}/tools/{tool_id}")
async def remove_tool_from_assistant(
    assistant_id: UUID, tool_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Удалить инструмент у ассистента"""
    # Проверяем существование связи
    query = select(AssistantToolLink).where(
        AssistantToolLink.assistant_id == assistant_id,
        AssistantToolLink.tool_id == tool_id,
        AssistantToolLink.is_active == True,
    )
    result = await session.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(
            status_code=404, detail="Tool is not linked to this assistant"
        )

    # Деактивируем связь (soft delete)
    link.is_active = False
    await session.commit()

    return {"message": "Tool successfully unlinked from assistant"}


@router.get("/assistants/{assistant_id}/tools")
async def get_assistant_tools(
    assistant_id: UUID, session: AsyncSession = Depends(get_session)
):
    """Получить список инструментов ассистента"""
    # Проверяем существование ассистента
    assistant = await session.get(Assistant, assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")

    # Получаем все активные связи
    query = select(AssistantToolLink).where(
        AssistantToolLink.assistant_id == assistant_id,
        AssistantToolLink.is_active == True,
    )
    result = await session.execute(query)
    links = result.scalars().all()

    # Получаем инструменты
    tools = []
    for link in links:
        tool = await session.get(Tool, link.tool_id)
        if tool:
            tools.append(tool)

    return tools
