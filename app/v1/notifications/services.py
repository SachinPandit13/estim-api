from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.v1.notifications.models import Notification
from app.v1.notifications.schemas import NotificationCreate


class NotificationService:
    @staticmethod
    def get_user_notifications(
        db: Session, user_id: Optional[str] = None, limit: int = 50
    ) -> list[Notification]:
        query = db.query(Notification).filter(Notification.is_deleted == False)
        if user_id:
            query = query.filter(
                (Notification.user_id == user_id) | (Notification.user_id.is_(None))
            )
        return query.order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def mark_read(db: Session, notification_id: str) -> Optional[Notification]:
        notif = (
            db.query(Notification)
            .filter(
                Notification.id == notification_id, Notification.is_deleted == False
            )
            .first()
        )
        if not notif:
            return None
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notif)
        return notif

    @staticmethod
    def mark_all_read(db: Session, user_id: Optional[str] = None) -> int:
        query = db.query(Notification).filter(
            Notification.is_read == False, Notification.is_deleted == False
        )
        if user_id:
            query = query.filter(Notification.user_id == user_id)
        count = query.update({"is_read": True, "read_at": datetime.now(timezone.utc)})
        db.commit()
        return count

    @staticmethod
    def create(db: Session, payload: NotificationCreate) -> Notification:
        notif = Notification(
            user_id=payload.user_id,
            incident_id=payload.incident_id,
            camera_id=payload.camera_id,
            title=payload.title,
            message=payload.message,
            severity=payload.severity,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif
