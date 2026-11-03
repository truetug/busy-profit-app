"""Explicit integration settings for request parsing and infographic wording."""

from pydantic import BaseModel, Field


class AnalyticsProfile(BaseModel):
    """Describe an application's telemetry contract without importing its code."""

    endpoints: frozenset[str] = Field(min_length=1)
    session_endpoint: str
    log_pattern: str = "*.json"
    device_header: str = "X-Device-ID"
    device_pattern: str = r"[A-Za-z0-9_-]{1,128}"
    uppercase_device_id: bool = False
    session_header: str = "X-Session-ID"
    uptime_header: str = "X-Uptime-Seconds"
    details_header: str = "X-Details-Count"


class InfographicLabels(BaseModel):
    """Keep product names and device terminology outside the SVG implementation."""

    title: str = "Application usage in the last seven days"
    devices: str = "devices"
