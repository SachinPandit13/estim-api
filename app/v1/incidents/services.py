from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.v1.incidents.models import SafetyIncident
from app.v1.users.models import User
from app.v1.incidents.schemas import IncidentCreate, IncidentResolve
from app.v1.incidents.functions import determine_severity



class IncidentService:
    @staticmethod
    def get_all(
        db: Session,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        camera_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SafetyIncident]:
        query = db.query(SafetyIncident).filter(SafetyIncident.is_deleted == False)
        if status:
            query = query.filter(SafetyIncident.status == status)
        if severity:
            query = query.filter(SafetyIncident.severity == severity)
        if camera_id:
            query = query.filter(SafetyIncident.camera_id == camera_id)
        return query.order_by(SafetyIncident.last_detected_at.desc()).offset(offset).limit(limit).all()

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

        new_incident = SafetyIncident(
            camera_id=camera_id,
            zone_id=zone_id,
            incident_type=event_type,
            severity=determine_severity(event_type),
            status="open",
            first_detected_at=now,
            last_detected_at=now,
            detection_count=1,
            evidence_snapshot=snapshot_url,
        )
        db.add(new_incident)
        db.commit()
        db.refresh(new_incident)
        return new_incident
