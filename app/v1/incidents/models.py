import uuid
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SafetyIncident(Base):
    __tablename__ = "safety_incidents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    incident_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(50), nullable=False, default="medium", index=True)
    camera_id = Column(String, ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True)
    zone_id = Column(String, ForeignKey("camera_zones.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), nullable=False, default="open", index=True)
    first_detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    last_detected_at = Column(DateTime(timezone=True), nullable=False)
    detection_count = Column(Integer, nullable=False, default=1)
    evidence_snapshot = Column(String(1024), nullable=True)
    assigned_to_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    notifications = relationship("Notification", back_populates="incident")
