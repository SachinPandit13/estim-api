"""Persist evidence JPEG snapshots for incidents/events."""

from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.db.config import settings

logger = logging.getLogger("estim.ai.evidence")


def ensure_snapshots_dir() -> str:
    path = settings.SNAPSHOTS_DIR or "uploads/snapshots"
    os.makedirs(path, exist_ok=True)
    return path


def save_snapshot_base64(image_base64: Optional[str], camera_id: str, prefix: str = "incident") -> Optional[str]:
    """Decode base64 frame and write JPEG. Returns URL path relative to API root."""
    if not image_base64:
        return None
    try:
        raw = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
        data = base64.b64decode(raw)
        folder = ensure_snapshots_dir()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{prefix}_{camera_id[:8]}_{ts}_{uuid.uuid4().hex[:8]}.jpg"
        full = os.path.join(folder, filename)
        with open(full, "wb") as f:
            f.write(data)
        # Served via StaticFiles at /uploads/...
        rel = full.replace("\\", "/")
        if not rel.startswith("uploads"):
            rel = f"uploads/snapshots/{filename}"
        return f"/{rel}" if not rel.startswith("/") else rel
    except Exception as exc:
        logger.warning("Failed to save snapshot: %s", exc)
        return None


def save_snapshot_ndarray(frame_rgb, camera_id: str, prefix: str = "incident") -> Optional[str]:
    try:
        from PIL import Image
        import numpy as np

        folder = ensure_snapshots_dir()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        filename = f"{prefix}_{camera_id[:8]}_{ts}_{uuid.uuid4().hex[:8]}.jpg"
        full = os.path.join(folder, filename)
        Image.fromarray(np.asarray(frame_rgb)).save(full, format="JPEG", quality=85)
        rel = full.replace("\\", "/")
        if not rel.startswith("uploads"):
            rel = f"uploads/snapshots/{filename}"
        return f"/{rel}" if not rel.startswith("/") else rel
    except Exception as exc:
        logger.warning("Failed to save ndarray snapshot: %s", exc)
        return None
