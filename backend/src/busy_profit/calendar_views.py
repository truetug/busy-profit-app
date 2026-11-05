"""Timezone-aware aggregation independent of HTTP and storage drivers."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo


class ClosingTotals(Protocol):
    """Expose cumulative values at real calendar boundaries."""

    def close(self, boundary: datetime, maximum_gap: int = 7200) -> int | None:
        """Return a covered cumulative close or unknown.

        The implementation owns timestamp lookup and coverage checks.
        """
        ...


def difference(before: int | None, after: int | None) -> int | None:
    """Keep missing coverage and downward corrections distinct from zero.

    Only a covered nonnegative delta represents a sales total.
    """
    return after - before if before is not None and after is not None and after >= before else None


def daily_values(source: ClosingTotals, start: date, days: int, timezone: str) -> list[int | None]:
    """Aggregate local calendar days using independent midnight boundaries.

    Calendar arithmetic preserves 23-hour and 25-hour DST days.
    """
    zone = ZoneInfo(timezone)
    boundaries = [
        datetime.combine(start + timedelta(days=index), time.min, zone)
        for index in range(days + 1)
    ]
    closes = [source.close(boundary) for boundary in boundaries]
    return [difference(before, after) for before, after in zip(closes, closes[1:])]


def hourly_values(source: ClosingTotals, day: date, timezone: str) -> tuple[list[datetime], list[int | None]]:
    """Walk real UTC hours between consecutive local midnights.

    Repeated wall-clock hours retain distinct offsets and remain distinguishable.
    """
    zone = ZoneInfo(timezone)
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    boundaries = []
    cursor = start
    while cursor < end:
        boundaries.append(cursor)
        cursor += timedelta(hours=1)
    boundaries.append(end)
    closes = [source.close(boundary) for boundary in boundaries]
    return (
        [boundary.astimezone(zone) for boundary in boundaries[:-1]],
        [difference(before, after) for before, after in zip(closes, closes[1:])],
    )
