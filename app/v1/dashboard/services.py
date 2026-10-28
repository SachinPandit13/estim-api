from sqlalchemy import func
from sqlalchemy.orm import Session
from app.v1.cameras.models import Camera
from app.v1.incidents.models import SafetyIncident
from app.v1.dashboard.schemas import DashboardSummary
from app.v1.dashboard.functions import get_today_utc_range


class DashboardService:
    @staticmethod
    def get_summary(db: Session) -> DashboardSummary:
        start_today, now = get_today_utc_range()

        total_cameras = db.query(Camera).filter(Camera.is_deleted == False).count()
        online_cameras = db.query(Camera).filter(Camera.status == "online", Camera.is_deleted == False).count()

        open_incidents_today = (
            db.query(SafetyIncident)
            .filter(
                SafetyIncident.status == "open",
                SafetyIncident.last_detected_at >= start_today,
                SafetyIncident.is_deleted == False,
            )
            .count()
        )

        critical_incidents_today = (
            db.query(SafetyIncident)
            .filter(
                SafetyIncident.severity == "critical",
                SafetyIncident.last_detected_at >= start_today,
                SafetyIncident.is_deleted == False,
            )
            .count()
        )

        breakdown_rows = (
            db.query(SafetyIncident.incident_type, func.count(SafetyIncident.id))
            .filter(SafetyIncident.last_detected_at >= start_today, SafetyIncident.is_deleted == False)
            .group_by(SafetyIncident.incident_type)
            .all()
        )

        violations_by_type = {row[0]: row[1] for row in breakdown_rows}

        return DashboardSummary(
            total_cameras=total_cameras,
            online_cameras=online_cameras,
            open_incidents_today=open_incidents_today,
            critical_incidents_today=critical_incidents_today,
            violations_by_type=violations_by_type,
        )
