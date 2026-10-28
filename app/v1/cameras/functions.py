import re
from typing import Optional


def sanitize_rtsp_url(url: str) -> str:
    """Mask credentials in RTSP url for safe logging and responses."""
    if not url:
        return ""
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", url)


def build_cvr_rtsp_url(host: str, port: int, channel: int, username: str = "", password: str = "") -> str:
    """Build standardized CP Plus DVR RTSP URL string."""
    creds = f"{username}:{password}@" if username and password else ""
    return f"rtsp://{creds}{host}:{port}/cam/realmonitor?channel={channel}&subtype=0"
