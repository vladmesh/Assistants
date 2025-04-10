import re
from uuid import UUID

from database import get_session
from fastapi import APIRouter, Depends, HTTPException
from models.assistant import Tool, ToolType
from pydantic import BaseModel, validator
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter()


class ToolCreate(BaseModel):
    name: str
    tool_type: str  # Исправлено с type на tool_type
    description: str
    input_schema: str
    assistant_id: UUID = None  # Для sub_assistant, ссылка на ассистента,
    # которого вызывает данный инструмент
    is_active: bool = True

    @validator("name")
    def validate_name(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Tool name must contain only Latin letters, numbers, underscores and hyphens"
            )
        return v


class ToolUpdate(BaseModel):
    name: str = None
    tool_type: str = None  # Исправлено с type на tool_type
    description: str = None
    input_schema: str = None
    is_active: bool = None

    @validator("name")
    def validate_name(cls, v):
        if v is not None and not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Tool name must contain only Latin letters, numbers, underscores and hyphens"
            )
        return v


@router.get("/tools/")
async def list_tools(
    session: AsyncSession = Depends(get_session), skip: int = 0, limit: int = 100
):
    """Получить список всех инструментов"""
    query = select(Tool).offset(skip).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/tools/{tool_id}")
async def get_tool(tool_id: UUID, session: AsyncSession = Depends(get_session)):
    """Получить инструмент по ID"""
    tool = await session.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.post("/tools/")
async def create_tool(tool: ToolCreate, session: AsyncSession = Depends(get_session)):
    """Создать новый инструмент"""
    # Преобразуем строку в enum
    tool_data = tool.model_dump()
    print(f"Received tool data: {tool_data}")  # Добавляем отладочный вывод

    if tool_data["tool_type"] not in [t.value for t in ToolType]:
        raise HTTPException(status_code=400, detail="Invalid tool type")
    tool_data["tool_type"] = ToolType(tool_data["tool_type"])

    db_tool = Tool(**tool_data)
    session.add(db_tool)
    await session.commit()
    await session.refresh(db_tool)
    return db_tool


@router.put("/tools/{tool_id}")
async def update_tool(
    tool_id: UUID, tool_update: ToolUpdate, session: AsyncSession = Depends(get_session)
):
    """Обновить инструмент"""
    db_tool = await session.get(Tool, tool_id)
    if not db_tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    tool_data = tool_update.model_dump(exclude_unset=True)

    # Преобразуем строку в enum, если тип указан
    if "tool_type" in tool_data:  # Исправлено с type на tool_type
        if tool_data["tool_type"] not in [
            t.value for t in ToolType
        ]:  # Исправлено с type на tool_type
            raise HTTPException(status_code=400, detail="Invalid tool type")
        tool_data["tool_type"] = ToolType(
            tool_data["tool_type"]
        )  # Исправлено с type на tool_type

    for key, value in tool_data.items():
        setattr(db_tool, key, value)

    await session.commit()
    await session.refresh(db_tool)
    return db_tool


@router.delete("/tools/{tool_id}")
async def delete_tool(tool_id: UUID, session: AsyncSession = Depends(get_session)):
    """Удалить инструмент"""
    tool = await session.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    await session.delete(tool)
    await session.commit()
    return {"message": "Tool deleted successfully"}
