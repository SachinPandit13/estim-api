"""Helper formatting functions for notifications."""

def format_incident_notification_title(incident_type: str, camera_name: str) -> str:
    cleaned = incident_type.replace("_", " ").title()
    return f"Safety Alert: {cleaned} on {camera_name}"
