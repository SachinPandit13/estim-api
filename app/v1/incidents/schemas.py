from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class IncidentBase(BaseModel):
    incident_type: str
    severity: str = "medium"
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    status: str = "open"
    first_detected_at: datetime
    last_detected_at: datetime
    detection_count: int = 1
    evidence_snapshot: Optional[str] = None


class IncidentCreate(IncidentBase):
    pass


class IncidentResolve(BaseModel):
    resolution_notes: str


class IncidentRead(IncidentBase):
    id: str
    assigned_to_id: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
