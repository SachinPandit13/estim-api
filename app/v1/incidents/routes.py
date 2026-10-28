from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.v1.incidents.schemas import IncidentRead, IncidentResolve
from app.v1.incidents.services import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=list[IncidentRead])
def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return IncidentService.get_all(db, status, severity, camera_id, limit, offset)


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = IncidentService.get_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{incident_id}/acknowledge", response_model=IncidentRead)
def acknowledge_incident(incident_id: str, user_id: str = "current_user", db: Session = Depends(get_db)):
    incident = IncidentService.acknowledge(db, incident_id, user_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{incident_id}/resolve", response_model=IncidentRead)
def resolve_incident(incident_id: str, payload: IncidentResolve, db: Session = Depends(get_db)):
    incident = IncidentService.resolve(db, incident_id, payload)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
