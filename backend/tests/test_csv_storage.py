"""Tests for rolling, monthly, and published sales CSV histories."""

from datetime import UTC, datetime, timedelta

import pytest

from busy_profit.csv_storage import CsvHistoryRepository, DisplayHistoryCsvPublisher
from busy_profit.models import SalesObservation


def observation(at: datetime, bars_sold: int) -> SalesObservation:
    """Build a typed test observation with matching source and capture times."""
    return SalesObservation(
        observed_at=at,
        bars_sold=bars_sold,
        source_updated_at=at,
    )


def test_repository_keeps_28_days_and_archives_by_calendar_month(tmp_path) -> None:
    """Prune expired rolling rows while preserving month-partitioned archives."""
    rolling_path = tmp_path / "history.csv"
    repository = CsvHistoryRepository(rolling_path)
    now = datetime(2026, 10, 30, 12, tzinfo=UTC)
    old_point = observation(now - timedelta(days=29), 100)
    retained_point = observation(now - timedelta(days=1), 200)
    repository.append(rolling_path, old_point)
    repository.append(rolling_path.with_name("history-2026-09.csv"), old_point)
    repository.append(rolling_path, retained_point)

    points = repository.save(observation(now, 300))

    assert [point.bars_sold for point in points] == [200, 300]
    assert [point.bars_sold for point in repository.read(rolling_path)] == [200, 300]
    assert [
        point.bars_sold for point in repository.read(tmp_path / "history-2026-09.csv")
    ] == [100]
    assert [
        point.bars_sold for point in repository.read(tmp_path / "history-2026-10.csv")
    ] == [300]


def test_repository_rejects_unknown_csv_schema(tmp_path) -> None:
    """Fail loudly on a malformed file instead of hiding potentially lost data."""
    path = tmp_path / "history.csv"
    path.write_text("timestamp,count\n2026-10-30,5\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid sales history CSV header"):
        CsvHistoryRepository(path).read()


def test_display_publisher_keeps_recent_hourly_points(tmp_path) -> None:
    """Preserve hourly detail for short graphs and the prior-day comparison."""
    path = tmp_path / "public" / "history.csv"
    publisher = DisplayHistoryCsvPublisher(path, "UTC")
    first = observation(datetime(2026, 10, 30, 10, 5, tzinfo=UTC), 500)
    latest = observation(datetime(2026, 10, 30, 10, 55, tzinfo=UTC), 510)
    next_hour = observation(datetime(2026, 10, 30, 11, 2, tzinfo=UTC), 511)

    publisher.publish([first, latest, next_hour])

    points = CsvHistoryRepository(path).read()
    assert [(point.observed_at, point.bars_sold) for point in points] == [
        (latest.observed_at, 510),
        (next_hour.observed_at, 511),
    ]


def test_display_publisher_sparsifies_old_days_but_keeps_recent_49_hours(tmp_path) -> None:
    """Reduce a ten-day hourly history to daily anchors and the latest 49 hours."""
    path = tmp_path / "public" / "history.csv"
    publisher = DisplayHistoryCsvPublisher(path, "UTC")
    start = datetime(2026, 10, 20, 12, tzinfo=UTC)
    points = [
        observation(start + timedelta(hours=hour), 1000 + hour)
        for hour in range(10 * 24 + 1)
    ]

    publisher.publish(points)

    published = CsvHistoryRepository(path).read()
    assert len(published) == 57
    assert published[-49].observed_at == datetime(2026, 10, 28, 12, tzinfo=UTC)
    assert published[-1] == points[-1]
    assert published[0].observed_at == datetime(2026, 10, 20, 23, tzinfo=UTC)
