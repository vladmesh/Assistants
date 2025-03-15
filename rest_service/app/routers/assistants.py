from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid import UUID
from pydantic import BaseModel

from app.models.assistant import Assistant, AssistantType
from app.database import get_session

router = APIRouter()

class AssistantCreate(BaseModel):
    name: str
    is_secretary: bool = False
    model: str
    instructions: str
    assistant_type: str = AssistantType.LLM.value  # Принимаем строку
    openai_assistant_id: str = None

class AssistantUpdate(BaseModel):
    name: str = None
    is_secretary: bool = None
    model: str = None
    instructions: str = None
    assistant_type: str = None  # Принимаем строку
    openai_assistant_id: str = None
    is_active: bool = None

@router.get("/assistants/")
async def list_assistants(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100
):
    """Получить список всех ассистентов"""
    query = select(Assistant).offset(skip).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()

@router.get("/assistants/{assistant_id}")
async def get_assistant(
    assistant_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """Получить ассистента по ID"""
    assistant = await session.get(Assistant, assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return assistant

@router.post("/assistants/")
async def create_assistant(
    assistant: AssistantCreate,
    session: AsyncSession = Depends(get_session)
):
    """Создать нового ассистента"""
    # Преобразуем строку в enum
    assistant_data = assistant.model_dump()
    if assistant_data["assistant_type"] not in [t.value for t in AssistantType]:
        raise HTTPException(status_code=400, detail="Invalid assistant type")
    assistant_data["assistant_type"] = AssistantType(assistant_data["assistant_type"])
    
    db_assistant = Assistant(**assistant_data)
    session.add(db_assistant)
    await session.commit()
    await session.refresh(db_assistant)
    return db_assistant

@router.put("/assistants/{assistant_id}")
async def update_assistant(
    assistant_id: UUID,
    assistant_update: AssistantUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Обновить ассистента"""
    db_assistant = await session.get(Assistant, assistant_id)
    if not db_assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    assistant_data = assistant_update.model_dump(exclude_unset=True)
    
    # Преобразуем строку в enum, если тип указан
    if "assistant_type" in assistant_data:
        if assistant_data["assistant_type"] not in [t.value for t in AssistantType]:
            raise HTTPException(status_code=400, detail="Invalid assistant type")
        assistant_data["assistant_type"] = AssistantType(assistant_data["assistant_type"])
    
    for key, value in assistant_data.items():
        setattr(db_assistant, key, value)
    
    await session.commit()
    await session.refresh(db_assistant)
    return db_assistant

@router.delete("/assistants/{assistant_id}")
async def delete_assistant(
    assistant_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """Удалить ассистента"""
    assistant = await session.get(Assistant, assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    await session.delete(assistant)
    await session.commit()
    return {"message": "Assistant deleted successfully"} 