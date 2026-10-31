from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from jose import jwt
from sqlalchemy.orm import Session
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from app.db.session import get_db
from app.v1.auth.functions import SECRET_KEY, ALGORITHM
from app.v1.incidents.schemas import IncidentRead, IncidentResolve
from app.v1.incidents.services import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=Page[IncidentRead])
def list_incidents(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Legacy limit compatibility"),
    db: Session = Depends(get_db),
):
    actual_size = limit if limit is not None else size
    params = Params(page=page, size=actual_size)
    query = IncidentService.get_query(db, status, severity, camera_id)
    return paginate(query, params)


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    incident = IncidentService.get_by_id(db, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{incident_id}/acknowledge", response_model=IncidentRead)
def acknowledge_incident(
    incident_id: str,
    user_id: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    resolved_user_id = user_id
    if (not resolved_user_id or resolved_user_id == "current_user") and authorization:
        if authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            try:
                decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                resolved_user_id = decoded.get("sub")
            except Exception:
                pass

    incident = IncidentService.acknowledge(db, incident_id, resolved_user_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident



@router.patch("/{incident_id}/resolve", response_model=IncidentRead)
def resolve_incident(incident_id: str, payload: IncidentResolve, db: Session = Depends(get_db)):
    incident = IncidentService.resolve(db, incident_id, payload)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident
