import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class CameraZone(Base):
    __tablename__ = "camera_zones"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    camera_id = Column(String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    roi_polygon = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    camera = relationship("Camera", back_populates="zones")
