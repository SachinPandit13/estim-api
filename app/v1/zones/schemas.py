from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class ZoneBase(BaseModel):
    camera_id: str
    name: str
    description: Optional[str] = None
    roi_polygon: Optional[list[list[float]]] = None
    is_active: bool = True


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    roi_polygon: Optional[list[list[float]]] = None
    is_active: Optional[bool] = None


class ZoneRead(ZoneBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
