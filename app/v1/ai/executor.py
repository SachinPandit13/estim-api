"""Thread-pool inference executor so FastAPI request threads stay responsive."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional, TypeVar

from app.db.config import settings

logger = logging.getLogger("estim.ai.executor")

T = TypeVar("T")

_pool: Optional[ThreadPoolExecutor] = None


def start_executor() -> None:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=max(1, settings.AI_MAX_WORKERS), thread_name_prefix="estim-ai")
        logger.info("AI inference executor started workers=%s", settings.AI_MAX_WORKERS)


def stop_executor() -> None:
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None
        logger.info("AI inference executor stopped")


def run_inference(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Submit work to the pool and wait. Falls back to inline if pool not started."""
    if _pool is None:
        return fn(*args, **kwargs)
    fut: Future = _pool.submit(fn, *args, **kwargs)
    return fut.result(timeout=60)


def submit_inference(fn: Callable[..., T], *args: Any, **kwargs: Any) -> Future:
    start_executor()
    assert _pool is not None
    return _pool.submit(fn, *args, **kwargs)
