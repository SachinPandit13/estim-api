"""Estim multi-model AI safety pipeline."""

__all__ = ["get_ai_health", "get_camera_ai_health", "run_inference"]


def __getattr__(name: str):
    if name in ("get_ai_health", "get_camera_ai_health"):
        from app.v1.ai.health import get_ai_health, get_camera_ai_health

        return get_ai_health if name == "get_ai_health" else get_camera_ai_health
    if name == "run_inference":
        from app.v1.ai.executor import run_inference

        return run_inference
    raise AttributeError(name)
