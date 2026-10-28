from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class CameraBase(BaseModel):
    name: str
    description: Optional[str] = None
    source_type: str = "rtsp"
    stream_url: Optional[str] = None
    dvr_channel: Optional[int] = None
    location: Optional[str] = None
    is_enabled: bool = True
    config: Optional[dict[str, Any]] = None


class CameraCreate(CameraBase):
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_type: Optional[str] = None
    stream_url: Optional[str] = None
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None
    dvr_channel: Optional[int] = None
    location: Optional[str] = None
    is_enabled: Optional[bool] = None
    config: Optional[dict[str, Any]] = None


class CameraRead(CameraBase):
    id: str
    status: str
    last_connected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CameraTestResponse(BaseModel):
    reachable: bool
    status: str
    message: str
    latency_ms: Optional[float] = None
