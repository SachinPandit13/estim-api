"""Per-camera multi-object tracking state (ByteTrack IDs + centroid fallback)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Optional

from app.db.config import settings


class ActiveTrack:
    def __init__(
        self,
        track_id: int,
        bbox: list[float],
        helmet_status: str = "unknown",
        vest_status: str = "unknown",
        is_fallen: bool = False,
        pose_status: str = "unknown",
    ):
        self.track_id = track_id
        self.bbox = bbox
        self.helmet_status = helmet_status
        self.vest_status = vest_status
        self.is_fallen = is_fallen
        self.pose_status = pose_status
        self.missing_frames = 0
        self.consecutive_violations: dict[str, int] = {}
        self.last_incident_time: dict[str, datetime] = {}
        now = datetime.now(timezone.utc)
        self.first_seen_at = now
        self.last_seen = now
        self.detection_confidence = 0.0

    @property
    def has_helmet(self) -> bool:
        return self.helmet_status == "compliant"

    @property
    def has_vest(self) -> bool:
        return self.vest_status == "compliant"

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.bbox[0] + self.bbox[2]) / 2.0, (self.bbox[1] + self.bbox[3]) / 2.0)


class CameraTrackerState:
    def __init__(self, miss_ttl: Optional[int] = None):
        self.tracks: dict[int, ActiveTrack] = {}
        self.next_id = 1
        self.frame_counter = 0
        self.miss_ttl = miss_ttl if miss_ttl is not None else settings.TRACK_MISS_TTL

    def reset(self) -> None:
        self.tracks.clear()
        self.next_id = 1
        self.frame_counter = 0

    def update(self, candidates: list[dict[str, Any]]) -> None:
        self.frame_counter += 1
        now = datetime.now(timezone.utc)

        if not candidates:
            dead_ids = []
            for tid, track in self.tracks.items():
                track.missing_frames += 1
                if track.missing_frames > self.miss_ttl:
                    dead_ids.append(tid)
            for tid in dead_ids:
                del self.tracks[tid]
            return

        matched_track_ids: set[int] = set()

        for cand in candidates:
            bbox = cand.get("bbox", [0.3, 0.2, 0.7, 0.85])
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0

            best_id = None
            preset_id = cand.get("assigned_track_id")
            if preset_id is not None and preset_id in self.tracks and preset_id not in matched_track_ids:
                best_id = preset_id
            else:
                best_dist = 0.40
                for tid, track in self.tracks.items():
                    if tid in matched_track_ids:
                        continue
                    tcx, tcy = track.centroid
                    dist = math.hypot(cx - tcx, cy - tcy)
                    if dist < best_dist:
                        best_dist = dist
                        best_id = tid

            helmet_status = cand.get("helmet_status", "unknown")
            vest_status = cand.get("vest_status", "unknown")
            # Bools from clients: only trust explicit False → violation.
            # Never promote True to compliant without helmet_status/vest_status (stops HUD false OK).
            if "helmet_status" not in cand and "has_helmet" in cand:
                helmet_status = "violation" if cand.get("has_helmet") is False else "unknown"
            if "vest_status" not in cand and "has_vest" in cand:
                vest_status = "violation" if cand.get("has_vest") is False else "unknown"

            if best_id is not None:
                track = self.tracks[best_id]
                id_changed = False
                track.bbox = [round(0.65 * track.bbox[i] + 0.35 * bbox[i], 4) for i in range(4)]
                if track.helmet_status != helmet_status or track.vest_status != vest_status:
                    # Clear stale PPE when association changes meaningfully
                    pass
                track.helmet_status = helmet_status
                track.vest_status = vest_status
                track.is_fallen = cand.get("is_fallen", False)
                track.pose_status = cand.get("pose_status", track.pose_status)
                track.detection_confidence = float(cand.get("confidence", track.detection_confidence))
                track.missing_frames = 0
                track.last_seen = now
                matched_track_ids.add(best_id)
                assigned_id = best_id
                _ = id_changed
            else:
                assigned_id = preset_id if preset_id is not None else self.next_id
                self.next_id = max(self.next_id + 1, int(assigned_id) + 1)
                new_track = ActiveTrack(
                    track_id=int(assigned_id),
                    bbox=bbox,
                    helmet_status=helmet_status,
                    vest_status=vest_status,
                    is_fallen=cand.get("is_fallen", False),
                    pose_status=cand.get("pose_status", "unknown"),
                )
                new_track.detection_confidence = float(cand.get("confidence", 0.0))
                self.tracks[int(assigned_id)] = new_track
                matched_track_ids.add(int(assigned_id))

            cand["assigned_track_id"] = int(assigned_id)

        dead_ids = []
        for tid, track in self.tracks.items():
            if tid not in matched_track_ids:
                track.missing_frames += 1
                if track.missing_frames > self.miss_ttl:
                    dead_ids.append(tid)
        for tid in dead_ids:
            del self.tracks[tid]


_camera_trackers: dict[str, CameraTrackerState] = {}


def get_camera_tracker(camera_id: str) -> CameraTrackerState:
    if camera_id not in _camera_trackers:
        _camera_trackers[camera_id] = CameraTrackerState()
    return _camera_trackers[camera_id]


def reset_camera_tracker(camera_id: str) -> None:
    tracker = _camera_trackers.get(camera_id)
    if tracker:
        tracker.reset()
    else:
        _camera_trackers[camera_id] = CameraTrackerState()


def drop_camera_tracker(camera_id: str) -> None:
    _camera_trackers.pop(camera_id, None)
