"""AI worker / model health reporting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.v1.ai.models.registry import get_model_status

# camera_id -> health dict (updated by workers / infer path)
_camera_health: dict[str, dict[str, Any]] = {}


def update_camera_health(camera_id: str, **fields: Any) -> None:
    current = _camera_health.get(camera_id, {})
    current.update(fields)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    _camera_health[camera_id] = current


def clear_camera_health(camera_id: str) -> None:
    _camera_health.pop(camera_id, None)


def get_camera_ai_health(camera_id: str) -> dict[str, Any]:
    models = get_model_status()
    h = _camera_health.get(camera_id, {})
    worker_alive = bool(h.get("worker_alive", False))
    last_inference = h.get("last_inference_at")
    processing = bool(h.get("processing", False))

    if worker_alive and last_inference:
        ai_state = "LIVE"
    elif worker_alive and processing:
        ai_state = "PROCESSING"
    elif worker_alive:
        ai_state = "DEGRADED"
    elif models.get("person", {}).get("ready") and last_inference:
        # Push-based webcam infer without RTSP worker
        ai_state = "LIVE"
    elif models.get("person", {}).get("ready"):
        ai_state = "OFFLINE"
    else:
        ai_state = "OFFLINE"

    return {
        "camera_id": camera_id,
        "ai_state": ai_state,
        "worker_alive": worker_alive,
        "processing": processing,
        "last_inference_at": last_inference,
        "last_frame_at": h.get("last_frame_at"),
        "fps_actual": h.get("fps_actual"),
        "inference_ms": h.get("inference_ms"),
        "reconnect_count": h.get("reconnect_count", 0),
        "last_error": h.get("last_error"),
        "models_ready": {
            "person": models.get("person", {}).get("ready", False),
            "ppe": models.get("ppe", {}).get("ready", False),
            "fire_smoke": models.get("fire_smoke", {}).get("ready", False),
            "pose": models.get("pose", {}).get("ready", False),
        },
    }


def get_ai_health() -> dict[str, Any]:
    return {
        "models": get_model_status(),
        "cameras": {cid: get_camera_ai_health(cid) for cid in _camera_health},
    }
