from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.models import TelegramUser
from app.database import get_session

router = APIRouter()

@router.post("/users/")
def create_user(telegram_id: str, username: str = None, session: Session = Depends(get_session)):
    user = TelegramUser(telegram_id=telegram_id, username=username)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@router.get("/users/")
def list_users(session: Session = Depends(get_session)):
    query = select(TelegramUser)
    return session.exec(query).all()
