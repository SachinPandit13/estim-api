from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.v1.detections.schemas import DetectionEventRead
from app.v1.detections.services import DetectionService

router = APIRouter(prefix="/detections", tags=["Detections"])


@router.get("", response_model=list[DetectionEventRead])
def list_detections(
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return DetectionService.get_all(db, camera_id, event_type, limit, offset)
