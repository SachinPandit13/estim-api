import uuid
from sqlalchemy import Column, String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(255), nullable=False)
    stream_url = Column(String(1024), nullable=True)
    location = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="offline")
    config = Column(JSON, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    detection_events = relationship("DetectionEvent", back_populates="camera")
    notifications = relationship("Notification", back_populates="camera")
