from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.v1.notifications.schemas import NotificationRead
from app.v1.notifications.services import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return NotificationService.get_user_notifications(db, user_id, limit)


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(notification_id: str, db: Session = Depends(get_db)):
    notif = NotificationService.mark_read(db, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif


@router.patch("/read-all", response_model=dict)
def mark_all_notifications_read(user_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    count = NotificationService.mark_all_read(db, user_id)
    return {"updated_count": count}
