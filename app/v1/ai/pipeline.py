"""Shared frame pipeline used by POST /infer and RTSP workers."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.db.config import settings
from app.v1.ai.evidence import save_snapshot_base64, save_snapshot_ndarray
from app.v1.ai.health import update_camera_health
from app.v1.ai.models.fire_smoke import detect_fire_smoke
from app.v1.ai.models.person import detect_and_track_persons
from app.v1.ai.models.ppe import inspect_ppe_for_person, run_ppe_model
from app.v1.ai.models.pose_fall import analyze_fall_for_person, bbox_fall_prefilter
from app.v1.ai.rules import evaluate_worker, status_to_bool_compliant
from app.v1.ai.scheduler import frame_cadence
from app.v1.ai.tracking import get_camera_tracker
from app.v1.detections.models import DetectionEvent
from app.v1.detections.schemas import TrackedObject
from app.v1.incidents.services import IncidentService
from app.v1.zones.models import CameraZone

logger = logging.getLogger("estim.ai.pipeline")


def is_point_in_polygon(x: float, y: float, polygon: Any) -> bool:
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


def enrich_candidates(img_rgb: np.ndarray, camera_id: str, candidates: list[dict[str, Any]]) -> list[str]:
    """Attach PPE / fall / pose to person candidates; return model hazards."""
    frame_cadence.tick(camera_id)
    ppe_dets = []
    hazards: list[str] = []

    if frame_cadence.should_run_ppe(camera_id):
        ppe_dets = run_ppe_model(img_rgb)

    if frame_cadence.should_run_fire(camera_id):
        hazards.extend(detect_fire_smoke(img_rgb))

    h, w = img_rgb.shape[:2]
    for cand in candidates:
        bbox = cand["bbox"]
        if "bbox_px" in cand:
            x1, y1, x2, y2 = cand["bbox_px"]
        else:
            x1 = int(bbox[0] * w)
            y1 = int(bbox[1] * h)
            x2 = int(bbox[2] * w)
            y2 = int(bbox[3] * h)

        helmet_status, vest_status, hconf, vconf = inspect_ppe_for_person(
            img_rgb, x1, y1, x2, y2, ppe_dets if ppe_dets else None
        )
        cand["helmet_status"] = helmet_status
        cand["vest_status"] = vest_status
        cand["helmet_confidence"] = hconf
        cand["vest_confidence"] = vconf
        cand["has_helmet"] = status_to_bool_compliant(helmet_status)
        cand["has_vest"] = status_to_bool_compliant(vest_status)

        run_pose = frame_cadence.should_run_pose(camera_id) or bbox_fall_prefilter(bbox)
        if run_pose:
            is_fallen, pose_status = analyze_fall_for_person(
                img_rgb, [x1, y1, x2, y2], {"bbox": bbox}
            )
            cand["is_fallen"] = is_fallen
            cand["pose_status"] = pose_status
        else:
            cand.setdefault("is_fallen", False)
            cand.setdefault("pose_status", "unknown")

    return hazards


def apply_rules_and_persist(
    db: Session,
    camera_id: str,
    candidates: list[dict[str, Any]],
    *,
    trigger_incidents: bool = True,
    environmental_hazards: Optional[list[str]] = None,
    image_base64: Optional[str] = None,
    frame_rgb: Optional[np.ndarray] = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    tracker = get_camera_tracker(camera_id)
    tracker.update(candidates)

    active_zones = (
        db.query(CameraZone)
        .filter(
            CameraZone.camera_id == camera_id,
            CameraZone.is_active == True,
            CameraZone.is_deleted == False,
        )
        .all()
    )

    tracked_workers: list[TrackedObject] = []
    violations_detected: list[str] = []
    hazards_detected: list[str] = list(environmental_hazards or [])
    zone_alerts: list[str] = []
    incident_created = False
    incident_id = None

    # Environmental / model hazards → DetectionEvent + incident
    for hazard in list(set(hazards_detected)):
        if trigger_incidents:
            snap = None
            if image_base64:
                snap = save_snapshot_base64(image_base64, camera_id, prefix=hazard.lower())
            elif frame_rgb is not None:
                snap = save_snapshot_ndarray(frame_rgb, camera_id, prefix=hazard.lower())
            event = DetectionEvent(
                camera_id=camera_id,
                zone_id=None,
                event_type=hazard,
                confidence=0.8,
                bounding_box=None,
                snapshot_url=snap,
                metadata_json={"source": "hazard"},
                detected_at=now,
            )
            db.add(event)
            db.commit()
            hazard_incident = IncidentService.process_detection(
                db=db,
                camera_id=camera_id,
                event_type=hazard,
                zone_id=None,
                snapshot_url=snap,
                cooldown_seconds=min(30, settings.INCIDENT_COOLDOWN_SECONDS),
            )
            incident_created = True
            incident_id = hazard_incident.id

    for cand in candidates:
        track_id = cand.get("assigned_track_id", 1)
        active_track = tracker.tracks.get(track_id)
        bbox = active_track.bbox if active_track else cand.get("bbox", [0.3, 0.2, 0.7, 0.85])
        confidence = cand.get("confidence", 0.92)

        helmet_status = cand.get("helmet_status", "unknown")
        vest_status = cand.get("vest_status", "unknown")
        pose_status = cand.get("pose_status", "unknown")
        is_fallen = bool(cand.get("is_fallen", False))

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

        decision = evaluate_worker(
            helmet_status=helmet_status,
            vest_status=vest_status,
            is_fallen=is_fallen,
            pose_status=pose_status,
            zone_name=current_zone_name,
        )
        if decision.primary_violation:
            violations_detected.append(decision.primary_violation)

        if active_track and decision.primary_violation:
            curr_count = active_track.consecutive_violations.get(decision.primary_violation, 0) + 1
            active_track.consecutive_violations[decision.primary_violation] = curr_count
            if curr_count >= settings.TEMPORAL_CONFIRMATION_FRAMES and trigger_incidents:
                last_triggered = active_track.last_incident_time.get(decision.primary_violation)
                if not last_triggered or (now - last_triggered) > timedelta(seconds=45):
                    snap = None
                    if image_base64:
                        snap = save_snapshot_base64(image_base64, camera_id)
                    elif frame_rgb is not None:
                        snap = save_snapshot_ndarray(frame_rgb, camera_id)
                    event = DetectionEvent(
                        camera_id=camera_id,
                        zone_id=current_zone_id,
                        event_type=decision.primary_violation,
                        confidence=confidence,
                        bounding_box={
                            "x_min": bbox[0],
                            "y_min": bbox[1],
                            "x_max": bbox[2],
                            "y_max": bbox[3],
                            "track_id": track_id,
                        },
                        snapshot_url=snap,
                        metadata_json={
                            "track_id": track_id,
                            "helmet_status": helmet_status,
                            "vest_status": vest_status,
                            "pose_status": pose_status,
                            "has_helmet": status_to_bool_compliant(helmet_status),
                            "has_vest": status_to_bool_compliant(vest_status),
                            "is_fallen": decision.is_fallen,
                            "zone_name": current_zone_name,
                        },
                        detected_at=now,
                    )
                    db.add(event)
                    db.commit()
                    incident = IncidentService.process_detection(
                        db=db,
                        camera_id=camera_id,
                        event_type=decision.primary_violation,
                        zone_id=current_zone_id,
                        snapshot_url=snap,
                        cooldown_seconds=settings.INCIDENT_COOLDOWN_SECONDS,
                    )
                    incident_created = True
                    incident_id = incident.id
                    active_track.last_incident_time[decision.primary_violation] = now
        elif active_track:
            active_track.consecutive_violations.clear()

        tracked_workers.append(
            TrackedObject(
                track_id=track_id,
                class_name="worker",
                confidence=confidence,
                bbox=bbox,
                has_helmet=status_to_bool_compliant(helmet_status),
                has_vest=status_to_bool_compliant(vest_status),
                is_fallen=decision.is_fallen,
                helmet_status=helmet_status,
                vest_status=vest_status,
                pose_status=pose_status,
                violation_type=decision.primary_violation,
                current_zone_name=current_zone_name,
                status=decision.status,
            )
        )

    return {
        "tracked_workers": tracked_workers,
        "violations_detected": list(set(violations_detected)),
        "hazards_detected": list(set(hazards_detected)),
        "zone_alerts": zone_alerts,
        "incident_created": incident_created,
        "incident_id": incident_id,
        "timestamp": now,
    }


def process_bgr_frame(camera_id: str, frame_bgr: np.ndarray) -> None:
    """RTSP worker entry: infer + persist with a short-lived DB session."""
    t0 = time.perf_counter()
    frame_rgb = frame_bgr[:, :, ::-1].copy()
    candidates = detect_and_track_persons(frame_rgb, camera_id, is_rgb=True)
    hazards = enrich_candidates(frame_rgb, camera_id, candidates)

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        apply_rules_and_persist(
            db,
            camera_id,
            candidates,
            trigger_incidents=True,
            environmental_hazards=hazards,
            frame_rgb=frame_rgb,
        )
    finally:
        db.close()

    ms = (time.perf_counter() - t0) * 1000
    update_camera_health(
        camera_id,
        last_inference_at=datetime.now(timezone.utc).isoformat(),
        inference_ms=round(ms, 1),
        worker_alive=True,
        processing=True,
    )
