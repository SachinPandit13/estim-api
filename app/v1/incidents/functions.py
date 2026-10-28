"""Incident severity and grouping helpers."""

SEVERITY_MAPPING = {
    "fire": "critical",
    "smoke": "critical",
    "worker_fall": "high",
    "missing_helmet": "medium",
    "missing_vest": "low",
}


def determine_severity(incident_type: str) -> str:
    return SEVERITY_MAPPING.get(incident_type, "medium")
