from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.v1.incidents.models import SafetyIncident
from app.v1.users.models import User
from app.v1.incidents.schemas import IncidentCreate, IncidentResolve
from app.v1.incidents.functions import determine_severity
from app.v1.notifications.models import Notification
from app.v1.ws.manager import ws_manager



class IncidentService:
    @staticmethod
    def get_query(
        db: Session,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
    ):
        """Return an ordered SQLAlchemy query for use with fastapi-pagination."""
        query = db.query(SafetyIncident).filter(SafetyIncident.is_deleted == False)
        if status:
            query = query.filter(SafetyIncident.status == status)
        if severity:
            query = query.filter(SafetyIncident.severity == severity)
        if camera_id:
            query = query.filter(SafetyIncident.camera_id == camera_id)
        return query.order_by(SafetyIncident.last_detected_at.desc())

    @staticmethod
    def get_all(
        db: Session,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SafetyIncident]:
        return IncidentService.get_query(db, status, severity, camera_id).offset(offset).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, incident_id: str) -> Optional[SafetyIncident]:
        return db.query(SafetyIncident).filter(SafetyIncident.id == incident_id, SafetyIncident.is_deleted == False).first()

    @staticmethod
    def acknowledge(db: Session, incident_id: str, user_id: Optional[str] = None) -> Optional[SafetyIncident]:
        incident = IncidentService.get_by_id(db, incident_id)
        if not incident:
            return None
        incident.status = "acknowledged"

        # Validate that user_id exists in users table to prevent ForeignKeyViolation
        assigned_user = None
        if user_id and user_id != "current_user":
            assigned_user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()

        if assigned_user:
            incident.assigned_to_id = assigned_user.id
        else:
            # Fallback to the first active user/admin if available, or None
            first_user = db.query(User).filter(User.is_deleted == False).first()
            incident.assigned_to_id = first_user.id if first_user else None

        incident.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(incident)
        return incident

    @staticmethod
    def resolve(db: Session, incident_id: str, payload: IncidentResolve) -> Optional[SafetyIncident]:
        incident = IncidentService.get_by_id(db, incident_id)
        if not incident:
            return None
        incident.status = "resolved"
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolution_notes = payload.resolution_notes
        db.commit()
        db.refresh(incident)
        return incident

    @staticmethod
    def process_detection(
        db: Session,
        camera_id: str,
        event_type: str,
        zone_id: Optional[str] = None,
        snapshot_url: Optional[str] = None,
        cooldown_seconds: int = 60,
    ) -> SafetyIncident:
        """Deduplicates raw detection into an active incident or creates a new one."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)
        existing = (
            db.query(SafetyIncident)
            .filter(
                SafetyIncident.camera_id == camera_id,
                SafetyIncident.incident_type == event_type,
                SafetyIncident.status == "open",
                SafetyIncident.last_detected_at >= cutoff,
                SafetyIncident.is_deleted == False,
            )
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.last_detected_at = now
            existing.detection_count += 1
            if snapshot_url:
                existing.evidence_snapshot = snapshot_url
            db.commit()
            db.refresh(existing)
            return existing

        severity = determine_severity(event_type)
        new_incident = SafetyIncident(
            camera_id=camera_id,
            zone_id=zone_id,
            incident_type=event_type,
            severity=severity,
            status="open",
            first_detected_at=now,
            last_detected_at=now,
            detection_count=1,
            evidence_snapshot=snapshot_url,
        )
        db.add(new_incident)
        db.commit()
        db.refresh(new_incident)

        # Automatically record Notification and broadcast real-time WebSocket alert to admins
        clean_title = f"Safety Violation: {event_type.replace('_', ' ').title()}"
        clean_msg = f"Camera '{camera_id}' reported {event_type.replace('_', ' ')} incident requiring attention."
        notif = Notification(
            incident_id=new_incident.id,
            camera_id=camera_id,
            title=clean_title,
            message=clean_msg,
            severity=severity,
        )
        db.add(notif)
        db.commit()

        # Real-time WebSocket broadcast to all connected dashboards
        ws_manager.broadcast_sync({
            "type": "SAFETY_ALERT",
            "incident_id": new_incident.id,
            "event_type": event_type,
            "camera_id": camera_id,
            "zone_id": zone_id,
            "severity": severity,
            "title": clean_title,
            "message": clean_msg,
            "timestamp": now.isoformat(),
        })

        return new_incident
