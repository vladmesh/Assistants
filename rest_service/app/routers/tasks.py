from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models import Task, TaskStatus
from app.database import get_session

from app.models import TelegramUser

router = APIRouter()


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus
    user_id: int

class TaskUpdateRequest(BaseModel):
    title: Optional[str]
    status: Optional[TaskStatus]

    def dict_for_update(self):
        """Возвращает словарь только с установленными полями."""
        return {key: value for key, value in self.model_dump(exclude_unset=True).items() if value is not None}


@router.get("/tasks/")
async def list_tasks(session: AsyncSession = Depends(get_session)):
    print("Получаем все")
    query = select(Task)
    result = await session.execute(query)
    return result.scalars().all()

@router.get("/tasks/{task_id}")
async def get_task(task_id: int, session: AsyncSession = Depends(get_session)):
    """Получить таску по id."""
    print("Получаем одну")
    query = select(Task).where(Task.id == task_id)
    result = await session.execute(query)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/tasks/active/{user_id}")
async def get_active_tasks_for_user(user_id: int, session: AsyncSession = Depends(get_session)):
    """
    Get all active tasks for a specific user.
    """
    # Define the query to filter by user_id and active status
    query = select(Task).where(Task.user_id == user_id, Task.status == TaskStatus.ACTIVE)
    result = await session.execute(query)
    active_tasks = result.scalars().all()
    return active_tasks

@router.patch("/tasks/{task_id}")
async def update_task(task_id: int, update_data: TaskUpdateRequest, session: AsyncSession = Depends(get_session)):
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Применяем изменения только к указанным полям
    updates = update_data.dict_for_update()
    for key, value in updates.items():
        setattr(task, key, value)

    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task

@router.post("/tasks/")
async def create_task(task_data: TaskCreate, session: AsyncSession = Depends(get_session)):
    """
    Создание новой задачи.
    """
    user = await session.get(TelegramUser, task_data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Создаём задачу
    task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        user_id=task_data.user_id,
    )

    # Сохраняем задачу в базе данных
    session.add(task)
    await session.commit()
    await session.refresh(task)

    return task