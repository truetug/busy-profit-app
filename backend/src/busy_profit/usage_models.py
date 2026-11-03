"""Validated internal events for private device usage statistics."""

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from pydantic import BaseModel, Field


class UsageEvent(BaseModel):
    """Represent one feed request without credentials or account information."""

    at: datetime
    hardware_id: str = Field(pattern=r"^([0-9A-F]{24})?$")
    endpoint: str
    status: int = Field(ge=100, le=599)
    ip: IPv4Address | IPv6Address
