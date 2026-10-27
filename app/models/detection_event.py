import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    camera_id = Column(
        String,
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = Column(String(100), nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    snapshot_url = Column(String(1024), nullable=True)
    video_clip_url = Column(String(1024), nullable=True)
    metadata_json = Column("metadata", JSON, nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    camera = relationship("Camera", back_populates="detection_events")
    notifications = relationship("Notification", back_populates="detection_event")
