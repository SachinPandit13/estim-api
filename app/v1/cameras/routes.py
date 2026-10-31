from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.v1.cameras.schemas import (
    CameraRead,
    CameraCreate,
    CameraUpdate,
    CameraTestResponse,
    CameraAiHealth,
)
from app.v1.cameras.services import CameraService
from app.v1.ai.health import get_camera_ai_health

router = APIRouter(prefix="/cameras", tags=["Cameras"])


def _enrich_camera(camera) -> CameraRead:
    cfg = camera.config or {}
    data = CameraRead.model_validate(camera)
    data.dvr_host = cfg.get("dvr_host")
    data.dvr_port = cfg.get("dvr_port")
    data.subtype = cfg.get("subtype")
    data.rtsp_username = camera.rtsp_username
    try:
        health = get_camera_ai_health(camera.id)
        data.ai_state = health.get("ai_state")
    except Exception:
        data.ai_state = "OFFLINE"
    return data


@router.get("", response_model=list[CameraRead])
def list_cameras(db: Session = Depends(get_db)):
    return [_enrich_camera(c) for c in CameraService.get_all(db)]


@router.post("", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    return _enrich_camera(CameraService.create(db, payload))


@router.get("/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    camera = CameraService.get_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _enrich_camera(camera)


@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(camera_id: str, payload: CameraUpdate, db: Session = Depends(get_db)):
    camera = CameraService.update(db, camera_id, payload)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _enrich_camera(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    ok = CameraService.soft_delete(db, camera_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Camera not found")
    return None


@router.get("/{camera_id}/ai-health", response_model=CameraAiHealth)
def camera_ai_health(camera_id: str, db: Session = Depends(get_db)):
    camera = CameraService.get_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return get_camera_ai_health(camera_id)


@router.post("/{camera_id}/test", response_model=CameraTestResponse)
def test_camera_stream(camera_id: str, db: Session = Depends(get_db)):
    camera = CameraService.get_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraService.test_connection(camera, db=db)


@router.patch("/{camera_id}/toggle", response_model=CameraRead)
def toggle_camera(camera_id: str, db: Session = Depends(get_db)):
    camera = CameraService.toggle_enabled(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _enrich_camera(camera)
