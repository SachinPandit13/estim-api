"""Detection event CRUD + frame inference orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.v1.ai.executor import run_inference
from app.v1.ai.health import update_camera_health
from app.v1.ai.models.person import detect_and_track_persons
from app.v1.ai.pipeline import apply_rules_and_persist, enrich_candidates, is_point_in_polygon
from app.v1.ai.tracking import get_camera_tracker, reset_camera_tracker, drop_camera_tracker
from app.v1.detections.models import DetectionEvent
from app.v1.detections.schemas import (
    DetectionEventCreate,
    FrameInferenceRequest,
    FrameInferenceResponse,
)
from app.v1.detections.yolo_service import yolo_service

# Re-exports for older imports
__all__ = [
    "DetectionService",
    "get_camera_tracker",
    "reset_camera_tracker",
    "drop_camera_tracker",
    "is_point_in_polygon",
]


def _decode_rgb(image_base64: Optional[str]) -> Optional[Any]:
    if not image_base64:
        return None
    img = yolo_service.decode_image_base64(image_base64)
    if img is None:
        return None
    return np.array(img)


def _infer_candidates(payload: FrameInferenceRequest) -> tuple[list[dict[str, Any]], list[str], Optional[Any]]:
    img_rgb = _decode_rgb(payload.image_base64)
    candidates: list[dict[str, Any]] = []
    hazards: list[str] = list(payload.environmental_hazards or [])

    if img_rgb is not None and yolo_service.is_available:
        candidates = detect_and_track_persons(img_rgb, payload.camera_id, is_rgb=True)
        if candidates:
            hazards.extend(enrich_candidates(img_rgb, payload.camera_id, candidates))
            if payload.simulated_detections:
                for i, cand in enumerate(candidates):
                    if i < len(payload.simulated_detections):
                        sim = payload.simulated_detections[i]
                        if sim.get("has_helmet") is False:
                            cand["has_helmet"] = False
                            cand["helmet_status"] = "violation"
                        if sim.get("has_vest") is False:
                            cand["has_vest"] = False
                            cand["vest_status"] = "violation"
                        if sim.get("is_fallen") is True:
                            cand["is_fallen"] = True
                            cand["pose_status"] = "fall_transition"
        elif payload.simulated_detections is not None:
            candidates = _normalize_sim_candidates(payload.simulated_detections)
    elif payload.simulated_detections is not None:
        candidates = _normalize_sim_candidates(payload.simulated_detections)

    return candidates, hazards, img_rgb


def _normalize_sim_candidates(sims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Client-only sims: never promote weak color CV True → compliant (stops false Helmet/Vest OK)."""
    out: list[dict[str, Any]] = []
    for sim in sims:
        c = dict(sim)
        if "helmet_status" not in sim:
            # Explicit test override no-helmet, else default violation for visible worker sims
            c["helmet_status"] = "violation"
            c["has_helmet"] = False
        if "vest_status" not in sim:
            c["vest_status"] = "violation"
            c["has_vest"] = False
        out.append(c)
    return out


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
            # Accept short filters fire/smoke as well as FIRE_DETECTED
            et = event_type.strip()
            if et.lower() == "fire":
                query = query.filter(DetectionEvent.event_type.in_(["FIRE_DETECTED", "fire", "fire_detected"]))
            elif et.lower() == "smoke":
                query = query.filter(DetectionEvent.event_type.in_(["SMOKE_DETECTED", "smoke", "smoke_detected"]))
            else:
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
        def _work() -> tuple[list[dict[str, Any]], list[str], Optional[Any]]:
            return _infer_candidates(payload)

        candidates, hazards, img_rgb = run_inference(_work)

        result = apply_rules_and_persist(
            db,
            payload.camera_id,
            candidates,
            trigger_incidents=payload.trigger_incidents,
            environmental_hazards=hazards,
            image_base64=payload.image_base64,
            frame_rgb=img_rgb,
        )

        update_camera_health(
            payload.camera_id,
            last_inference_at=datetime.now(timezone.utc).isoformat(),
        )

        return FrameInferenceResponse(
            camera_id=payload.camera_id,
            timestamp=result["timestamp"],
            tracked_workers=result["tracked_workers"],
            violations_detected=result["violations_detected"],
            hazards_detected=result["hazards_detected"],
            incident_created=result["incident_created"],
            incident_id=result["incident_id"],
            zone_alerts=result["zone_alerts"],
        )
