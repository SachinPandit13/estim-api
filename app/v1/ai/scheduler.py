"""Per-camera frame cadence for staggered specialty models."""

from __future__ import annotations

from app.db.config import settings


class FrameCadence:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def tick(self, camera_id: str) -> int:
        n = self._counters.get(camera_id, 0) + 1
        self._counters[camera_id] = n
        return n

    def should_run_ppe(self, camera_id: str) -> bool:
        n = self._counters.get(camera_id, 0)
        return n % max(1, settings.PPE_CADENCE) == 0

    def should_run_fire(self, camera_id: str) -> bool:
        n = self._counters.get(camera_id, 0)
        return n % max(1, settings.FIRE_SMOKE_CADENCE) == 0

    def should_run_pose(self, camera_id: str) -> bool:
        n = self._counters.get(camera_id, 0)
        return n % max(1, settings.POSE_CADENCE) == 0

    def reset(self, camera_id: str) -> None:
        self._counters.pop(camera_id, None)


frame_cadence = FrameCadence()
