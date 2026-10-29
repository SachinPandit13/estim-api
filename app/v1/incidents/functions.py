"""Incident severity and grouping helpers."""

SEVERITY_MAPPING = {
    "fire": "critical",
    "smoke": "critical",
    "worker_fall": "critical",
    "worker_fall_detected": "critical",
    "missing_helmet": "medium",
    "no_helmet": "medium",
    "missing_vest": "low",
    "no_vest": "low",
    "zone_intrusion": "high",
    "forklift_proximity": "high",
}


def determine_severity(incident_type: str) -> str:
    key = incident_type.strip().lower() if incident_type else ""
    return SEVERITY_MAPPING.get(key, "medium")

