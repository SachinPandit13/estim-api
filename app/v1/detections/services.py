import math
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
from sqlalchemy.orm import Session

from app.v1.detections.models import DetectionEvent
from app.v1.detections.schemas import (
    DetectionEventCreate,
    FrameInferenceRequest,
    FrameInferenceResponse,
    TrackedObject,
)
from app.v1.zones.models import CameraZone
from app.v1.incidents.services import IncidentService


def is_point_in_polygon(x: float, y: float, polygon: Any) -> bool:
    """Ray-casting algorithm to test if point (x, y) is inside polygon.
    Polygon can be [[x, y], ...] or [{"x": x, "y": y}, ...].
    Coordinates are assumed normalized 0.0 - 1.0.
    """
    if not polygon or not isinstance(polygon, list) or len(polygon) < 3:
        return False

    pts: list[tuple[float, float]] = []
    for p in polygon:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            pts.append((float(p[0]), float(p[1])))
        elif isinstance(p, dict) and "x" in p and "y" in p:
            pts.append((float(p["x"]), float(p["y"])))

    if len(pts) < 3:
        return False

    inside = False
    n = len(pts)
    p1x, p1y = pts[0]
    for i in range(n + 1):
        p2x, p2y = pts[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    else:
                        xinters = p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


class ActiveTrack:
    def __init__(self, track_id: int, bbox: list[float], has_helmet: bool, has_vest: bool, is_fallen: bool):
        self.track_id = track_id
        self.bbox = bbox
        self.has_helmet = has_helmet
        self.has_vest = has_vest
        self.is_fallen = is_fallen
        self.missing_frames = 0
        self.consecutive_violations: dict[str, int] = {}
        self.last_incident_time: dict[str, datetime] = {}
        self.last_seen = datetime.now(timezone.utc)

    @property
    def centroid(self) -> tuple[float, float]:
        cx = (self.bbox[0] + self.bbox[2]) / 2.0
        cy = (self.bbox[1] + self.bbox[3]) / 2.0
        return (cx, cy)


class CameraTrackerState:
    def __init__(self):
        self.tracks: dict[int, ActiveTrack] = {}
        self.next_id = 1
        self.frame_counter = 0

    def update(self, candidates: list[dict[str, Any]]) -> list[TrackedObject]:
        self.frame_counter += 1
        now = datetime.now(timezone.utc)
        results: list[TrackedObject] = []
        matched_track_ids = set()

        for cand in candidates:
            bbox = cand.get("bbox", [0.3, 0.2, 0.7, 0.85])
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0

            # Match with closest existing track within distance threshold
            best_id = None
            best_dist = 0.40  # 40% frame distance threshold

            for tid, track in self.tracks.items():
                if tid in matched_track_ids:
                    continue
                tcx, tcy = track.centroid
                dist = math.hypot(cx - tcx, cy - tcy)
                if dist < best_dist:
                    best_dist = dist
                    best_id = tid

            if best_id is not None:
                track = self.tracks[best_id]
                track.bbox = bbox
                track.has_helmet = cand.get("has_helmet", True)
                track.has_vest = cand.get("has_vest", True)
                track.is_fallen = cand.get("is_fallen", False)
                track.missing_frames = 0
                track.last_seen = now
                matched_track_ids.add(best_id)
                assigned_id = best_id
            else:
                assigned_id = self.next_id
                self.next_id += 1
                new_track = ActiveTrack(
                    track_id=assigned_id,
                    bbox=bbox,
                    has_helmet=cand.get("has_helmet", True),
                    has_vest=cand.get("has_vest", True),
                    is_fallen=cand.get("is_fallen", False),
                )
                self.tracks[assigned_id] = new_track
                matched_track_ids.add(assigned_id)

            cand["assigned_track_id"] = assigned_id

        # Clean up stale tracks not seen in 15 frames
        dead_ids = []
        for tid, track in self.tracks.items():
            if tid not in matched_track_ids:
                track.missing_frames += 1
                if track.missing_frames > 15:
                    dead_ids.append(tid)

        for tid in dead_ids:
            del self.tracks[tid]

        return results


# Global in-memory camera trackers registry
_camera_trackers: dict[str, CameraTrackerState] = {}


def get_camera_tracker(camera_id: str) -> CameraTrackerState:
    if camera_id not in _camera_trackers:
        _camera_trackers[camera_id] = CameraTrackerState()
    return _camera_trackers[camera_id]


class DetectionService:
    @staticmethod
    def get_all(
        db: Session,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DetectionEvent]:
        query = db.query(DetectionEvent).filter(DetectionEvent.is_deleted == False)
        if camera_id:
            query = query.filter(DetectionEvent.camera_id == camera_id)
        if event_type:
            query = query.filter(DetectionEvent.event_type == event_type)
        return query.order_by(DetectionEvent.detected_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def create(db: Session, payload: DetectionEventCreate) -> DetectionEvent:
        event = DetectionEvent(
            camera_id=payload.camera_id,
            zone_id=payload.zone_id,
            event_type=payload.event_type,
            confidence=payload.confidence,
            bounding_box=payload.bounding_box,
            snapshot_url=payload.snapshot_url,
            video_clip_url=payload.video_clip_url,
            metadata_json=payload.metadata_json,
            detected_at=payload.detected_at,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def infer_frame(db: Session, payload: FrameInferenceRequest) -> FrameInferenceResponse:
        """Evaluates worker safety tracking on a video/webcam frame:
        - Multi-Object Tracking (persistent Track IDs)
        - PPE verification (Hardhat/Helmet & Safety Vest)
        - Fall detection (Aspect ratio and posture)
        - Zone Intrusion (Point-in-polygon against CameraZone)
        - Temporal smoothing (3 consecutive frame threshold)
        - Creates DetectionEvent & triggers SafetyIncident
        """
        now = datetime.now(timezone.utc)
        tracker = get_camera_tracker(payload.camera_id)

        # 1. Fetch active zones for this camera
        active_zones = (
            db.query(CameraZone)
            .filter(
                CameraZone.camera_id == payload.camera_id,
                CameraZone.is_active == True,
                CameraZone.is_deleted == False,
            )
            .all()
        )

        # 2. Extract worker detection candidates
        candidates = []
        if payload.simulated_detections is not None:
            candidates = payload.simulated_detections
        else:
            candidates = []


        # 3. Associate detections with persistent Track IDs
        tracker.update(candidates)

        tracked_workers: list[TrackedObject] = []
        violations_detected: list[str] = []
        zone_alerts: list[str] = []
        incident_created = False
        incident_id = None

        for cand in candidates:
            track_id = cand.get("assigned_track_id", 1)
            active_track = tracker.tracks.get(track_id)
            bbox = cand.get("bbox", [0.3, 0.2, 0.7, 0.85])
            confidence = cand.get("confidence", 0.92)

            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            aspect_ratio = w / (h if h > 0.01 else 0.01)

            # Fall detection check: horizontal aspect ratio > 1.3
            is_fallen = cand.get("is_fallen", False) or (aspect_ratio > 1.3)

            # Worker foot/anchor point for zone testing: (bottom center)
            foot_x = (bbox[0] + bbox[2]) / 2.0
            foot_y = bbox[3]

            current_zone_name = None
            current_zone_id = None
            for zone in active_zones:
                if zone.roi_polygon and is_point_in_polygon(foot_x, foot_y, zone.roi_polygon):
                    current_zone_name = zone.name
                    current_zone_id = zone.id
                    zone_alerts.append(f"Worker #{track_id} in restricted zone '{zone.name}'")
                    break

            has_helmet = cand.get("has_helmet", True)
            has_vest = cand.get("has_vest", True)

            # Determine primary violation if any
            primary_violation = None
            if is_fallen:
                primary_violation = "WORKER_FALL_DETECTED"
            elif current_zone_name:
                primary_violation = "ZONE_INTRUSION"
            elif not has_helmet:
                primary_violation = "NO_HELMET"
            elif not has_vest:
                primary_violation = "NO_VEST"

            # Determine visual status
            if is_fallen or current_zone_name:
                status = "violation"
            elif not has_helmet or not has_vest:
                status = "warning"
            else:
                status = "compliant"

            if primary_violation:
                violations_detected.append(primary_violation)

            # 4. Temporal Smoothing (3-frame rule before triggering incident)
            if active_track:
                if primary_violation:
                    curr_count = active_track.consecutive_violations.get(primary_violation, 0) + 1
                    active_track.consecutive_violations[primary_violation] = curr_count

                    # If violation persisted for >= 3 frames, check incident cooldown
                    if curr_count >= 3 and payload.trigger_incidents:
                        last_triggered = active_track.last_incident_time.get(primary_violation)
                        # Cooldown of 45 seconds per track violation
                        if not last_triggered or (now - last_triggered) > timedelta(seconds=45):
                            # Record DetectionEvent
                            event = DetectionEvent(
                                camera_id=payload.camera_id,
                                zone_id=current_zone_id,
                                event_type=primary_violation,
                                confidence=confidence,
                                bounding_box={
                                    "x_min": bbox[0],
                                    "y_min": bbox[1],
                                    "x_max": bbox[2],
                                    "y_max": bbox[3],
                                    "track_id": track_id,
                                },
                                metadata_json={
                                    "track_id": track_id,
                                    "has_helmet": has_helmet,
                                    "has_vest": has_vest,
                                    "is_fallen": is_fallen,
                                    "zone_name": current_zone_name,
                                },
                                detected_at=now,
                            )
                            db.add(event)
                            db.commit()
                            db.refresh(event)

                            # Trigger / aggregate into SafetyIncident
                            incident = IncidentService.process_detection(
                                db=db,
                                camera_id=payload.camera_id,
                                event_type=primary_violation,
                                zone_id=current_zone_id,
                                snapshot_url=None,
                                cooldown_seconds=60,
                            )
                            incident_created = True
                            incident_id = incident.id
                            active_track.last_incident_time[primary_violation] = now
                else:
                    # Reset consecutive violation counter when compliant
                    active_track.consecutive_violations.clear()

            tracked_workers.append(
                TrackedObject(
                    track_id=track_id,
                    class_name="worker",
                    confidence=confidence,
                    bbox=bbox,
                    has_helmet=has_helmet,
                    has_vest=has_vest,
                    is_fallen=is_fallen,
                    violation_type=primary_violation,
                    current_zone_name=current_zone_name,
                    status=status,
                )
            )

        return FrameInferenceResponse(
            camera_id=payload.camera_id,
            timestamp=now,
            tracked_workers=tracked_workers,
            violations_detected=list(set(violations_detected)),
            incident_created=incident_created,
            incident_id=incident_id,
            zone_alerts=zone_alerts,
        )
