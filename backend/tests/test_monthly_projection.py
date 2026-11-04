"""Verify the UTC snapshot contract for the monthly archive."""

from datetime import datetime

from busy_profit.models import SalesObservation
from busy_profit.monthly_projection import hourly_utc_snapshots


def test_hourly_archive_preserves_totals_gaps_and_actual_utc_timestamps() -> None:
    """Select completed-hour closes regardless of input order or offset.

    Keep corrections and gaps intact for interpretation by the client.
    """
    points = []
    for timestamp, count in [
        ("2026-09-01T02:59:00+03:00", 101),
        ("2026-09-01T00:59:00+00:00", 100),
        ("2026-08-31T23:01:00+00:00", 99),
        ("2026-09-01T02:59:00+00:00", 103),
        ("2026-09-01T03:01:00+00:00", 104),
    ]:
        at = datetime.fromisoformat(timestamp)
        points.append(SalesObservation(observed_at=at, bars_sold=count, source_updated_at=at))
    snapshots = hourly_utc_snapshots(points, datetime.fromisoformat("2026-09-01T06:30:00+03:00"))
    assert [(point.observed_at.isoformat(), point.bars_sold) for point in snapshots] == [
        ("2026-08-31T23:59:00+00:00", 101),
        ("2026-09-01T00:59:00+00:00", 100),
        ("2026-09-01T02:59:00+00:00", 103),
    ]
