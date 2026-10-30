"""Person detection + per-camera ByteTrack."""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import numpy as np

from app.db.config import settings
from app.v1.ai.device import resolve_device
from app.v1.ai.models.registry import model_registry

logger = logging.getLogger("estim.ai.person")

# Ultralytics persist=True shares tracker state on the model object.
# Use a lock + camera-scoped track ID remapping via results; reset on reconnect.
_infer_lock = threading.Lock()
_last_camera_id: Optional[str] = None


def detect_and_track_persons(
    frame_bgr_or_rgb: np.ndarray,
    camera_id: str,
    conf_threshold: Optional[float] = None,
    *,
    is_rgb: bool = True,
) -> list[dict[str, Any]]:
    """Run person YOLO + ByteTrack. Returns normalized bbox candidates."""
    model = model_registry.ensure_person()
    if model is None:
        return []

    conf = conf_threshold if conf_threshold is not None else settings.DETECTION_CONFIDENCE_THRESHOLD
    img = frame_bgr_or_rgb
    if not is_rgb and img.ndim == 3 and img.shape[2] == 3:
        # OpenCV BGR → RGB for consistency with PIL path
        img = img[:, :, ::-1].copy()

    h, w = img.shape[:2]
    device = resolve_device()

    global _last_camera_id
    with _infer_lock:
        # ponytail: single Ultralytics tracker on shared model; switch camera resets tracker state
        if _last_camera_id is not None and _last_camera_id != camera_id:
            try:
                model.predictor = None  # force fresh tracker on next track()
            except Exception:
                pass
        _last_camera_id = camera_id

        try:
            results = model.track(
                source=img,
                persist=True,
                tracker="bytetrack.yaml",
                classes=[0],
                conf=conf,
                device=device,
                verbose=False,
            )
        except Exception as exc:
            logger.error("Person track failed camera=%s: %s", camera_id, exc)
            return []

    if not results:
        return []

    res = results[0]
    boxes = getattr(res, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    candidates: list[dict[str, Any]] = []
    for i, box in enumerate(boxes):
        xyxy = box.xyxy[0].tolist()
        x1_px, y1_px, x2_px, y2_px = xyxy
        norm_x1 = max(0.01, min(0.98, x1_px / w))
        norm_y1 = max(0.01, min(0.98, y1_px / h))
        norm_x2 = max(0.02, min(0.99, x2_px / w))
        norm_y2 = max(0.02, min(0.99, y2_px / h))
        confidence = float(box.conf[0]) if box.conf is not None else 0.5
        track_id = int(box.id[0]) if box.id is not None else (i + 1)
        candidates.append({
            "bbox": [round(norm_x1, 4), round(norm_y1, 4), round(norm_x2, 4), round(norm_y2, 4)],
            "bbox_px": [int(x1_px), int(y1_px), int(x2_px), int(y2_px)],
            "confidence": round(confidence, 2),
            "assigned_track_id": track_id,
        })
    return candidates


def reset_person_tracker(camera_id: str) -> None:
    global _last_camera_id
    with _infer_lock:
        model = model_registry.ensure_person()
        if model is not None:
            try:
                model.predictor = None
            except Exception:
                pass
        if _last_camera_id == camera_id:
            _last_camera_id = None
