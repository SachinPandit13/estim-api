import re
from typing import Optional, Any
from urllib.parse import urlparse, parse_qs


def sanitize_rtsp_url(url: str) -> str:
    """Mask credentials in RTSP url for safe logging and responses."""
    if not url:
        return ""
    return re.sub(r"://([^:@]+):([^@]+)@", r"://\1:***@", url)


def build_dvr_rtsp_url(
    host: str,
    port: int = 554,
    channel: int = 1,
    subtype: int = 0,
    username: str = "",
    password: str = "",
) -> str:
    """
    Build standardized dynamic Industrial DVR/NVR RTSP URL.
    Format: rtsp://USERNAME:PASSWORD@HOST:PORT/cam/realmonitor?channel=CHANNEL&subtype=SUBTYPE
    """
    creds = f"{username}:{password}@" if username and password else (f"{username}@" if username else "")
    clean_host = host.strip() if host else "127.0.0.1"
    clean_port = port if port and port > 0 else 554
    clean_channel = channel if channel and channel > 0 else 1
    clean_subtype = 1 if subtype == 1 else 0

    return f"rtsp://{creds}{clean_host}:{clean_port}/cam/realmonitor?channel={clean_channel}&subtype={clean_subtype}"


def build_cvr_rtsp_url(
    host: str, port: int = 554, channel: int = 1, username: str = "", password: str = ""
) -> str:
    """Backward-compatible alias for build_dvr_rtsp_url."""
    return build_dvr_rtsp_url(
        host=host, port=port, channel=channel, subtype=0, username=username, password=password
    )


def parse_rtsp_url(url: str) -> dict[str, Any]:
    """Parse dynamic RTSP url components for diagnostics and configuration extraction."""
    if not url:
        return {}

    try:
        # Standardize url for urlparse
        p = urlparse(url if "://" in url else f"rtsp://{url}")
        query = parse_qs(p.query)

        channel = 1
        subtype = 0
        if "channel" in query:
            try:
                channel = int(query["channel"][0])
            except (ValueError, IndexError):
                pass
        if "subtype" in query:
            try:
                subtype = int(query["subtype"][0])
            except (ValueError, IndexError):
                pass

        return {
            "scheme": p.scheme or "rtsp",
            "host": p.hostname or "",
            "port": p.port or 554,
            "username": p.username or "",
            "password": p.password or "",
            "path": p.path or "",
            "channel": channel,
            "subtype": subtype,
            "sanitized_url": sanitize_rtsp_url(url),
        }
    except Exception:
        return {"sanitized_url": sanitize_rtsp_url(url)}
