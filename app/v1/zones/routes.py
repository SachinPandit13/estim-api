from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.v1.zones.schemas import ZoneRead, ZoneCreate, ZoneUpdate
from app.v1.zones.services import ZoneService

router = APIRouter(prefix="/zones", tags=["Zones"])


@router.get("/camera/{camera_id}", response_model=list[ZoneRead])
def list_camera_zones(camera_id: str, db: Session = Depends(get_db)):
    return ZoneService.get_by_camera(db, camera_id)


@router.post("", response_model=ZoneRead, status_code=status.HTTP_201_CREATED)
def create_zone(payload: ZoneCreate, db: Session = Depends(get_db)):
    return ZoneService.create(db, payload)


@router.get("/{zone_id}", response_model=ZoneRead)
def get_zone(zone_id: str, db: Session = Depends(get_db)):
    zone = ZoneService.get_by_id(db, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone
