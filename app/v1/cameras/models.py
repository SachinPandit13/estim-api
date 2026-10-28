import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    source_type = Column(String(50), nullable=False, default="rtsp")
    stream_url = Column(String(1024), nullable=True)
    rtsp_username = Column(String(255), nullable=True)
    rtsp_password = Column(String(255), nullable=True)
    dvr_channel = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="offline")
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(1000), nullable=True)
    config = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    zones = relationship("CameraZone", back_populates="camera", cascade="all, delete-orphan")
    detection_events = relationship("DetectionEvent", back_populates="camera")
    notifications = relationship("Notification", back_populates="camera")
