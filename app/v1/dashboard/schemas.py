from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_cameras: int
    online_cameras: int
    open_incidents_today: int
    critical_incidents_today: int
    violations_by_type: dict[str, int]


class TimelinePoint(BaseModel):
    timestamp: str
    incident_count: int
    violation_type: str
