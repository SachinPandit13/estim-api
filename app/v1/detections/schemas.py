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


class TrackedObject(BaseModel):
    track_id: int
    class_name: str = "worker"
    confidence: float
    bbox: list[float]  # [x_min, y_min, x_max, y_max] normalized 0.0 - 1.0
    has_helmet: bool = True
    has_vest: bool = True
    is_fallen: bool = False
    violation_type: Optional[str] = None
    current_zone_name: Optional[str] = None
    status: str = "compliant"  # "compliant" | "warning" | "violation"


class FrameInferenceRequest(BaseModel):
    camera_id: str
    image_base64: Optional[str] = None
    trigger_incidents: bool = True
    simulated_detections: Optional[list[dict[str, Any]]] = None
    environmental_hazards: Optional[list[str]] = None


class FrameInferenceResponse(BaseModel):
    camera_id: str
    timestamp: datetime
    tracked_workers: list[TrackedObject]
    violations_detected: list[str]
    hazards_detected: list[str] = []
    incident_created: bool = False
    incident_id: Optional[str] = None
    zone_alerts: list[str] = []

