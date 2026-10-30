"""Lazy singleton model registry. Soft-fails when weights are missing."""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from app.db.config import settings
from app.v1.ai.device import resolve_device

logger = logging.getLogger("estim.ai.registry")


class ModelRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._person: Any = None
        self._ppe: Any = None
        self._fire_smoke: Any = None
        self._pose: Any = None
        self._person_ready = False
        self._ppe_ready = False
        self._fire_smoke_ready = False
        self._pose_ready = False
        self._person_names: dict[int, str] = {}
        self._ppe_names: dict[int, str] = {}
        self._fire_names: dict[int, str] = {}

    def ensure_person(self) -> Optional[Any]:
        if self._person_ready:
            return self._person
        with self._lock:
            if self._person_ready:
                return self._person
            self._person = self._load_yolo(settings.PERSON_MODEL_PATH or "yolov8n.pt")
            self._person_ready = self._person is not None
            if self._person is not None:
                self._person_names = dict(getattr(self._person, "names", {}) or {})
            return self._person

    def ensure_ppe(self) -> Optional[Any]:
        if not settings.ENABLE_PPE_MODEL or not settings.PPE_MODEL_PATH:
            return None
        if self._ppe_ready:
            return self._ppe
        with self._lock:
            if self._ppe_ready:
                return self._ppe
            self._ppe = self._load_yolo(settings.PPE_MODEL_PATH)
            self._ppe_ready = self._ppe is not None
            if self._ppe is not None:
                self._ppe_names = dict(getattr(self._ppe, "names", {}) or {})
                logger.info("PPE model classes: %s", self._ppe_names)
            return self._ppe

    def ensure_fire_smoke(self) -> Optional[Any]:
        if not settings.ENABLE_FIRE_SMOKE_MODEL or not settings.FIRE_SMOKE_MODEL_PATH:
            return None
        if self._fire_smoke_ready:
            return self._fire_smoke
        with self._lock:
            if self._fire_smoke_ready:
                return self._fire_smoke
            self._fire_smoke = self._load_yolo(settings.FIRE_SMOKE_MODEL_PATH)
            self._fire_smoke_ready = self._fire_smoke is not None
            if self._fire_smoke is not None:
                self._fire_names = dict(getattr(self._fire_smoke, "names", {}) or {})
                logger.info("Fire/smoke model classes: %s", self._fire_names)
            return self._fire_smoke

    def ensure_pose(self) -> Optional[Any]:
        if not settings.ENABLE_POSE_FALL_MODEL or not settings.POSE_MODEL_PATH:
            return None
        if self._pose_ready:
            return self._pose
        with self._lock:
            if self._pose_ready:
                return self._pose
            self._pose = self._load_yolo(settings.POSE_MODEL_PATH)
            self._pose_ready = self._pose is not None
            return self._pose

    def status(self) -> dict[str, Any]:
        # Trigger person load so health reflects readiness
        self.ensure_person()
        return {
            "device": resolve_device(),
            "person": {
                "ready": self._person_ready,
                "path": settings.PERSON_MODEL_PATH,
                "classes": self._person_names,
            },
            "ppe": {
                "enabled": settings.ENABLE_PPE_MODEL,
                "ready": self._ppe_ready,
                "path": settings.PPE_MODEL_PATH or None,
                "classes": self._ppe_names,
            },
            "fire_smoke": {
                "enabled": settings.ENABLE_FIRE_SMOKE_MODEL,
                "ready": self._fire_smoke_ready,
                "path": settings.FIRE_SMOKE_MODEL_PATH or None,
                "classes": self._fire_names,
            },
            "pose": {
                "enabled": settings.ENABLE_POSE_FALL_MODEL,
                "ready": self._pose_ready,
                "path": settings.POSE_MODEL_PATH or None,
            },
        }

    def _load_yolo(self, path: str) -> Optional[Any]:
        if not path:
            return None
        try:
            from ultralytics import YOLO

            model = YOLO(path)
            device = resolve_device()
            try:
                model.to(device)
            except Exception:
                pass
            logger.info("Loaded YOLO model %s on %s", path, device)
            return model
        except Exception as exc:
            logger.error("Failed to load YOLO model %s: %s", path, exc)
            return None


model_registry = ModelRegistry()


def get_model_status() -> dict[str, Any]:
    return model_registry.status()
