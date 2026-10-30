"""Thin facade over the multi-model AI person pipeline (backward compatible)."""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Optional

from app.v1.ai.models.registry import model_registry
from app.v1.ai.models.person import detect_and_track_persons
from app.v1.ai.models.ppe import inspect_ppe_for_person
from app.v1.ai.models.pose_fall import bbox_fall_prefilter
from app.v1.ai.rules import status_to_bool_compliant

logger = logging.getLogger("estim.yolo")

try:
    from PIL import Image
    import numpy as np

    _DEPS_OK = True
except Exception as err:
    Image = None  # type: ignore
    np = None  # type: ignore
    _DEPS_OK = False
    logger.info("YOLO deps pending (%s). Standby mode.", err)


class YoloInferenceService:
    _instance: Optional["YoloInferenceService"] = None

    def __new__(cls) -> "YoloInferenceService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        if _DEPS_OK:
            model_registry.ensure_person()

    @property
    def is_available(self) -> bool:
        return _DEPS_OK and model_registry.ensure_person() is not None

    def decode_image_base64(self, b64_str: str) -> Optional[Any]:
        if not b64_str or Image is None:
            return None
        try:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_str)
            return Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception as e:
            logger.warning("Failed to decode base64 frame: %s", e)
            return None

    def infer_and_track(
        self,
        image_base64: str,
        camera_id: str = "default",
        conf_threshold: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        img = self.decode_image_base64(image_base64)
        if img is None or np is None or not self.is_available:
            return []
        img_np = np.array(img)
        candidates = detect_and_track_persons(
            img_np, camera_id, conf_threshold=conf_threshold, is_rgb=True
        )
        h, w = img_np.shape[:2]
        for cand in candidates:
            bbox = cand["bbox"]
            if "bbox_px" in cand:
                x1, y1, x2, y2 = cand["bbox_px"]
            else:
                x1, y1 = int(bbox[0] * w), int(bbox[1] * h)
                x2, y2 = int(bbox[2] * w), int(bbox[3] * h)
            helmet_status, vest_status, _, _ = inspect_ppe_for_person(img_np, x1, y1, x2, y2)
            cand["helmet_status"] = helmet_status
            cand["vest_status"] = vest_status
            cand["has_helmet"] = status_to_bool_compliant(helmet_status)
            cand["has_vest"] = status_to_bool_compliant(vest_status)
            cand["is_fallen"] = bbox_fall_prefilter(bbox)
            cand["pose_status"] = "lying" if cand["is_fallen"] else "unknown"
        return candidates


yolo_service = YoloInferenceService()
