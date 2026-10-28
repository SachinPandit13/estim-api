"""Helpers for detection telemetry."""

ALLOWED_EVENT_TYPES = {
    "missing_helmet",
    "missing_vest",
    "worker_fall",
    "fire",
    "smoke",
}


def is_valid_event_type(event_type: str) -> bool:
    return event_type in ALLOWED_EVENT_TYPES
