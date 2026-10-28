from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class NotificationBase(BaseModel):
    user_id: Optional[str] = None
    incident_id: Optional[str] = None
    camera_id: Optional[str] = None
    title: str
    message: str
    severity: str = "info"


class NotificationCreate(NotificationBase):
    pass


class NotificationRead(NotificationBase):
    id: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
