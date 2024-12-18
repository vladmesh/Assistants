from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from app.models import TelegramUser
from app.database import get_session

router = APIRouter()

class UserCreate(BaseModel):
    telegram_id: int
    username: str = None

@router.post("/users/")
def create_user(user: UserCreate, session: Session = Depends(get_session)):
    print("post user")
    db_user = TelegramUser(telegram_id=user.telegram_id, username=user.username)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@router.get("/users/")
def get_user(telegram_id: int, session: Session = Depends(get_session)):
    """Получить пользователя по telegram_id."""
    query = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
    user = session.exec(query).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/users/all/")
def list_users(session: Session = Depends(get_session)):
    """Получить список всех пользователей."""
    query = select(TelegramUser)
    return session.exec(query).all()
