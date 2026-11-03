"""Define the BUSY Profit integration profile for reusable request analytics."""

from request_analytics import AnalyticsProfile, InfographicLabels

PROFILE = AnalyticsProfile(
    endpoints=frozenset({"/current.csv", "/older.csv", "/history.csv"}),
    session_endpoint="/current.csv",
    log_pattern="busy-profit-access*.json",
    device_header="X-Busy-Hardware-ID",
    device_pattern=r"[0-9A-F]{24}",
    uppercase_device_id=True,
    session_header="X-Busy-Session-ID",
    uptime_header="X-Busy-Uptime-Seconds",
    details_header="X-Busy-Details-Count",
)
LABELS = InfographicLabels(title="BUSY Profit usage in the last seven days", devices="bars")
