"""Helper aggregation calculators for dashboard analytics."""
from datetime import datetime, timezone, timedelta


def get_today_utc_range() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_day, now
