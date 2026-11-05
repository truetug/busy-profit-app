"""HTTP contracts for compact server-aggregated sales views."""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ViewQuery(BaseModel):
    """Validate calendar context without silently assuming the server timezone."""

    model_config = ConfigDict(extra="forbid")
    timezone: str = Field(max_length=64)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        """Require a supported named timezone.

        Unknown firmware aliases must be mapped explicitly before this boundary.
        """
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Unsupported timezone") from error
        return value


class DailyView(BaseModel):
    """Describe consecutive local dates using compact nullable sales values."""

    revision: str
    timezone: str
    start: date
    values: list[int | None] = Field(max_length=3660)
    total: int = Field(ge=0)
    more: bool


class HourlyView(BaseModel):
    """Preserve real chronological hours including repeated DST clock labels."""

    revision: str
    timezone: str
    date: date
    starts: list[datetime] = Field(min_length=23, max_length=25)
    values: list[int | None] = Field(min_length=23, max_length=25)
