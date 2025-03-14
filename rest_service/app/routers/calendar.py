from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import TelegramUser, CalendarCredentials
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/calendar", tags=["calendar"])

@router.put("/user/{user_id}/token")
async def update_calendar_token(
    user_id: int,
    access_token: str,
    refresh_token: str,
    token_expiry: datetime,
    db: Session = Depends(get_session)
):
    """Update user's Google Calendar token"""
    user = db.exec(select(TelegramUser).where(TelegramUser.id == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        # Get or create credentials
        credentials = db.exec(select(CalendarCredentials).where(
            CalendarCredentials.user_id == user_id
        )).first()
        
        if not credentials:
            credentials = CalendarCredentials(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=token_expiry
            )
            db.add(credentials)
        else:
            credentials.access_token = access_token
            credentials.refresh_token = refresh_token
            credentials.token_expiry = token_expiry
            credentials.updated_at = datetime.utcnow()
            
        db.commit()
        return {"message": "Token updated successfully"}
        
    except Exception as e:
        logger.error("Failed to update token", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update token")

@router.get("/user/{user_id}/token")
async def get_calendar_token(
    user_id: int,
    db: Session = Depends(get_session)
) -> Optional[Dict[str, Any]]:
    """Get user's Google Calendar token"""
    try:
        # Get credentials
        credentials = db.exec(select(CalendarCredentials).where(
            CalendarCredentials.user_id == user_id
        )).first()
        
        if not credentials:
            return None
            
        return {
            "access_token": credentials.access_token,
            "refresh_token": credentials.refresh_token,
            "token_expiry": credentials.token_expiry.isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get token", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get token") 