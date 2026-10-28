from typing import Optional
from sqlalchemy.orm import Session
from app.v1.zones.models import CameraZone
from app.v1.zones.schemas import ZoneCreate, ZoneUpdate


class ZoneService:
    @staticmethod
    def get_by_camera(db: Session, camera_id: str) -> list[CameraZone]:
        return db.query(CameraZone).filter(CameraZone.camera_id == camera_id, CameraZone.is_deleted == False).all()

    @staticmethod
    def get_by_id(db: Session, zone_id: str) -> Optional[CameraZone]:
        return db.query(CameraZone).filter(CameraZone.id == zone_id, CameraZone.is_deleted == False).first()

    @staticmethod
    def create(db: Session, payload: ZoneCreate) -> CameraZone:
        zone = CameraZone(
            camera_id=payload.camera_id,
            name=payload.name,
            description=payload.description,
            roi_polygon=payload.roi_polygon,
            is_active=payload.is_active,
        )
        db.add(zone)
        db.commit()
        db.refresh(zone)
        return zone
