"""Fire/smoke model slot - disabled until evaluated weights are configured."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.db.config import settings
from app.v1.ai.device import resolve_device
from app.v1.ai.models.registry import model_registry

logger = logging.getLogger("estim.ai.fire_smoke")


def detect_fire_smoke(img_rgb: np.ndarray) -> list[str]:
    """Return hazard event type strings e.g. FIRE_DETECTED, SMOKE_DETECTED."""
    model = model_registry.ensure_fire_smoke()
    if model is None:
        return []
    try:
        results = model.predict(
            source=img_rgb,
            conf=settings.DETECTION_CONFIDENCE_THRESHOLD,
            device=resolve_device(),
            verbose=False,
        )
    except Exception as exc:
        logger.error("Fire/smoke predict failed: %s", exc)
        return []
    if not results:
        return []
    names = dict(getattr(model, "names", {}) or {})
    hazards: list[str] = []
    boxes = getattr(results[0], "boxes", None)
    if boxes is None:
        return hazards
    for box in boxes:
        cls_id = int(box.cls[0]) if box.cls is not None else -1
        label = str(names.get(cls_id, "")).lower()
        conf = float(box.conf[0]) if box.conf is not None else 0.0
        if conf < settings.DETECTION_CONFIDENCE_THRESHOLD:
            continue
        if "smoke" in label:
            hazards.append("SMOKE_DETECTED")
        elif "fire" in label or "flame" in label:
            hazards.append("FIRE_DETECTED")
    return list(set(hazards))


def model_ready() -> bool:
    return (
        settings.ENABLE_FIRE_SMOKE_MODEL
        and bool(settings.FIRE_SMOKE_MODEL_PATH)
        and model_registry.ensure_fire_smoke() is not None
    )
