from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.models import Task, TaskStatus
from app.database import get_session

router = APIRouter()

@router.post("/tasks/")
def create_task(user_id: int, text: str, session: Session = Depends(get_session)):
    task = Task(user_id=user_id, text=text)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@router.get("/tasks/")
def list_tasks(session: Session = Depends(get_session)):
    query = select(Task)
    return session.exec(query).all()

@router.patch("/tasks/{task_id}/")
def update_task(task_id: int, status: TaskStatus, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        return {"error": "Task not found"}
    task.status = status
    session.add(task)
    session.commit()
    session.refresh(task)
    return task
