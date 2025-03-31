from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from models import TelegramUser
from database import get_session

router = APIRouter()

class UserCreate(BaseModel):
    telegram_id: int
    username: str = None

@router.post("/users/")
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_session)):
    db_user = TelegramUser(telegram_id=user.telegram_id, username=user.username)
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user

@router.get("/users/")
async def get_user(telegram_id: int, session: AsyncSession = Depends(get_session)):
    """Получить пользователя по telegram_id."""
    query = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/users/{user_id}")
async def get_user_by_id(user_id: int, session: AsyncSession = Depends(get_session)):
    """Получить пользователя по ID."""
    user = await session.get(TelegramUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/users/all/")
async def list_users(session: AsyncSession = Depends(get_session)):
    """Получить список всех пользователей."""
    query = select(TelegramUser)
    result = await session.execute(query)
    return result.scalars().all()
