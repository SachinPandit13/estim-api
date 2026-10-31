from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from app.db.session import get_db
from app.v1.detections.schemas import DetectionEventRead, FrameInferenceRequest, FrameInferenceResponse
from app.v1.detections.services import DetectionService

router = APIRouter(prefix="/detections", tags=["Detections"])


@router.get("", response_model=Page[DetectionEventRead])
def list_detections(
    camera_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Legacy limit compatibility"),
    db: Session = Depends(get_db),
):
    actual_size = limit if limit is not None else size
    params = Params(page=page, size=actual_size)
    query = DetectionService.get_query(db, camera_id, event_type)
    return paginate(query, params)


@router.post("/infer", response_model=FrameInferenceResponse)
def infer_frame(
    payload: FrameInferenceRequest,
    db: Session = Depends(get_db),
):
    return DetectionService.infer_frame(db, payload)

