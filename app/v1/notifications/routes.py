from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from app.db.session import get_db
from app.v1.notifications.schemas import NotificationRead
from app.v1.notifications.services import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=Page[NotificationRead])
def list_notifications(
    user_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size (default 10)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Legacy limit compatibility"),
    db: Session = Depends(get_db),
):
    actual_size = limit if limit is not None else size
    params = Params(page=page, size=actual_size)
    query = NotificationService.get_user_notifications_query(db, user_id)
    return paginate(query, params)


@router.get("/unread-count", response_model=dict)
def get_unread_count(
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    count = NotificationService.get_unread_count(db, user_id)
    return {"unread_count": count}


@router.patch("/read-all", response_model=dict)
def mark_all_notifications_read(
    user_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    count = NotificationService.mark_all_read(db, user_id)
    return {"updated_count": count}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(notification_id: str, db: Session = Depends(get_db)):
    notif = NotificationService.mark_read(db, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif


@router.patch("/{notification_id}/unread", response_model=NotificationRead)
def mark_notification_unread(notification_id: str, db: Session = Depends(get_db)):
    notif = NotificationService.mark_unread(db, notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notif
