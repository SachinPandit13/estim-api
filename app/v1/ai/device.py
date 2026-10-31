"""Resolve inference device once (cpu / cuda)."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.db.config import settings

logger = logging.getLogger("estim.ai.device")


@lru_cache(maxsize=1)
def resolve_device() -> str:
    preferred = (settings.AI_DEVICE or "auto").strip().lower()
    if preferred in ("cpu", "cuda"):
        if preferred == "cuda" and not _cuda_available():
            logger.warning("AI_DEVICE=cuda requested but CUDA unavailable; using cpu")
            return "cpu"
        return preferred

    if _cuda_available():
        logger.info("AI device resolved to cuda")
        return "cuda"
    logger.info("AI device resolved to cpu")
    return "cpu"


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False
