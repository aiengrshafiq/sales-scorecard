from datetime import datetime, timezone

# These helper functions are now in their own file to be shared across the application.

def ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensures a datetime object is timezone-aware, assuming UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

def time_ago(dt: datetime) -> str:
    """Converts a datetime object to a human-readable string like '2h ago'."""
    if not dt: return "N/A"
    now = datetime.now(timezone.utc)
    dt_aware = ensure_timezone_aware(dt)
    diff = now - dt_aware
    seconds = diff.total_seconds()
    if seconds < 60: return "Just now"
    if seconds < 3600: return f"{int(seconds / 60)}m ago"
    if seconds < 86400: return f"{int(seconds / 3600)}h ago"
    return f"{diff.days}d ago"