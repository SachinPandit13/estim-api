from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, field_validator
from app.v1.cameras.functions import sanitize_rtsp_url


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
    dvr_host: Optional[str] = None
    dvr_port: Optional[int] = 554
    subtype: Optional[int] = 0
    rtsp_username: Optional[str] = None
    rtsp_password: Optional[str] = None


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_type: Optional[str] = None
    stream_url: Optional[str] = None
    dvr_host: Optional[str] = None
    dvr_port: Optional[int] = None
    subtype: Optional[int] = None
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
    # Edit-form helpers (password never returned)
    dvr_host: Optional[str] = None
    dvr_port: Optional[int] = None
    subtype: Optional[int] = None
    rtsp_username: Optional[str] = None
    ai_state: Optional[str] = None

    @field_validator("stream_url", mode="after")
    @classmethod
    def mask_credentials(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_rtsp_url(v) if v else v

    model_config = ConfigDict(from_attributes=True)


class CameraAiHealth(BaseModel):
    camera_id: str
    ai_state: str
    worker_alive: bool = False
    processing: bool = False
    last_inference_at: Optional[str] = None
    last_frame_at: Optional[str] = None
    fps_actual: Optional[float] = None
    inference_ms: Optional[float] = None
    reconnect_count: int = 0
    last_error: Optional[str] = None
    models_ready: dict[str, bool] = {}


class CameraTestResponse(BaseModel):
    reachable: bool
    status: str
    message: str
    latency_ms: Optional[float] = None
