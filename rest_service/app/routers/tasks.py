from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select
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
        return {key: value for key, value in self.dict(exclude_unset=True).items() if value is not None}


@router.get("/tasks/")
def list_tasks(session: Session = Depends(get_session)):
    print("Получаем все")
    query = select(Task)
    return session.exec(query).all()

@router.get("/tasks/{task_id}")
def get_task(task_id: int, session: Session = Depends(get_session)):
    """Получить таску по id."""
    print("Получаем одну")
    query = select(Task).where(Task.id == task_id)
    task = session.exec(query).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task




@router.patch("/tasks/{task_id}")
def update_task(task_id: int, update_data: TaskUpdateRequest, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Применяем изменения только к указанным полям
    updates = update_data.dict_for_update()
    for key, value in updates.items():
        setattr(task, key, value)

    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@router.post("/tasks/")
def create_task(task_data: TaskCreate, session: Session = Depends(get_session)):
    """
    Создание новой задачи.
    """
    print(f"таска: {task_data}")
    user = session.get(TelegramUser, task_data.user_id)
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
    session.commit()
    session.refresh(task)

    return task