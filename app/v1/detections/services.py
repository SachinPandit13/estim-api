from typing import Optional
from sqlalchemy.orm import Session
from app.v1.detections.models import DetectionEvent
from app.v1.detections.schemas import DetectionEventCreate


class DetectionService:
    @staticmethod
    def get_all(
        db: Session,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DetectionEvent]:
        query = db.query(DetectionEvent).filter(DetectionEvent.is_deleted == False)
        if camera_id:
            query = query.filter(DetectionEvent.camera_id == camera_id)
        if event_type:
            query = query.filter(DetectionEvent.event_type == event_type)
        return query.order_by(DetectionEvent.detected_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def create(db: Session, payload: DetectionEventCreate) -> DetectionEvent:
        event = DetectionEvent(
            camera_id=payload.camera_id,
            zone_id=payload.zone_id,
            event_type=payload.event_type,
            confidence=payload.confidence,
            bounding_box=payload.bounding_box,
            snapshot_url=payload.snapshot_url,
            video_clip_url=payload.video_clip_url,
            metadata_json=payload.metadata_json,
            detected_at=payload.detected_at,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
