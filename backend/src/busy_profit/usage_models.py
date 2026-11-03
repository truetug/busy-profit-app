"""Validated internal events for private device usage statistics."""

from datetime import date, datetime
from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, Field


class UsageEvent(BaseModel):
    """Represent one feed request without credentials or account information."""

    at: datetime
    hardware_id: str = Field(pattern=r"^([0-9A-F]{24})?$")
    endpoint: str
    status: int = Field(ge=100, le=599)
    ip: IPv4Address | IPv6Address
    session_id: str = ""
    uptime_seconds: int = Field(default=0, ge=0, le=31536000)
    details_count: int = Field(default=0, ge=0, le=1000000)


class UsageDay(BaseModel):
    """Describe daily observed active devices, preserving unavailable history."""

    day: date
    active: int | None


class UsageSummary(BaseModel):
    """Expose aggregate-only public metrics without device or network identifiers."""

    generated_at: datetime
    active: int
    new: int
    returning: int
    regular: int
    starts: int | None
    details: int | None
    runtime_seconds: int | None
    session_since: datetime | None = None
    days: list[UsageDay]
