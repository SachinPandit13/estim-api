from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.v1.cameras.schemas import CameraRead, CameraCreate, CameraUpdate, CameraTestResponse
from app.v1.cameras.services import CameraService

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("", response_model=list[CameraRead])
def list_cameras(db: Session = Depends(get_db)):
    return CameraService.get_all(db)


@router.post("", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    return CameraService.create(db, payload)


@router.get("/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    camera = CameraService.get_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


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
    return camera
