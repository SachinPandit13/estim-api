"""YOLO-Pose fall slot + bbox aspect-ratio prefilter bridge."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from app.db.config import settings
from app.v1.ai.device import resolve_device
from app.v1.ai.models.registry import model_registry

logger = logging.getLogger("estim.ai.pose_fall")


def bbox_fall_prefilter(bbox: list[float]) -> bool:
    """Weak geometric prefilter only — not a confirmed fall."""
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    aspect = w / (h if h > 0.01 else 0.01)
    return aspect > 1.65 and bbox[3] > 0.80 and h < 0.30


def analyze_fall_for_person(
    img_rgb: np.ndarray,
    bbox_px: list[int],
    track_history: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """
    Returns (is_fallen_candidate, pose_status).
    Pose model when enabled; otherwise bbox prefilter → unknown/lying heuristic.
    """
    model = model_registry.ensure_pose()
    if model is None:
        bbox_norm_hint = track_history or {}
        bbox = bbox_norm_hint.get("bbox")
        if bbox and bbox_fall_prefilter(bbox):
            return True, "lying"
        return False, "unknown"

    try:
        results = model.predict(
            source=img_rgb,
            conf=settings.DETECTION_CONFIDENCE_THRESHOLD,
            device=resolve_device(),
            verbose=False,
        )
    except Exception as exc:
        logger.error("Pose predict failed: %s", exc)
        return False, "unknown"

    # Minimal keypoint rule: if pose available, use torso angle when keypoints present
    if not results or getattr(results[0], "keypoints", None) is None:
        return False, "unknown"

    kps = results[0].keypoints
    if kps is None or len(kps) == 0:
        return False, "unknown"

    # Use first pose whose center falls in person bbox
    x1, y1, x2, y2 = bbox_px
    for i in range(len(kps)):
        xy = kps.xy[i].cpu().numpy() if hasattr(kps.xy[i], "cpu") else np.array(kps.xy[i])
        if xy.shape[0] < 13:
            continue
        # COCO: 5=l_shoulder, 6=r_shoulder, 11=l_hip, 12=r_hip
        mid_shoulder = (xy[5] + xy[6]) / 2.0
        mid_hip = (xy[11] + xy[12]) / 2.0
        cx, cy = (mid_shoulder + mid_hip) / 2.0
        if not (x1 <= cx <= x2 and y1 <= cy <= y2):
            continue
        dx = mid_hip[0] - mid_shoulder[0]
        dy = mid_hip[1] - mid_shoulder[1]
        # Angle from vertical: large absolute atan2(dx, dy) ⇒ horizontal torso
        import math

        angle_from_vertical = abs(math.degrees(math.atan2(dx, dy)))
        if angle_from_vertical > 55 and mid_hip[1] > img_rgb.shape[0] * 0.55:
            return True, "fall_transition"
        if angle_from_vertical > 40:
            return False, "bending"
        return False, "standing"

    return False, "unknown"
