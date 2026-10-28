from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class DetectionEventBase(BaseModel):
    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    event_type: str
    confidence: float
    bounding_box: Optional[dict[str, Any]] = None
    snapshot_url: Optional[str] = None
    video_clip_url: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    detected_at: datetime


class DetectionEventCreate(DetectionEventBase):
    pass


class DetectionEventRead(DetectionEventBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
