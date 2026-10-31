"""Tests for rolling, monthly, and published sales CSV histories."""

import csv
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


def read_compact(path) -> list[SalesObservation]:
    """Read public rows and validate their exact two-column schema.

    Reconstruct the unused source timestamp only for comparisons in tests.
    """
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["observed_at", "bars_sold"]
        return [
            observation(datetime.fromisoformat(row["observed_at"]), int(row["bars_sold"]))
            for row in reader
        ]


def test_repository_keeps_38_days_and_archives_by_calendar_month(tmp_path) -> None:
    """Prune expired rolling rows while preserving month-partitioned archives."""
    rolling_path = tmp_path / "history.csv"
    repository = CsvHistoryRepository(rolling_path)
    now = datetime(2026, 10, 30, 12, tzinfo=UTC)
    old_point = observation(now - timedelta(days=39), 100)
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


def test_repository_restores_extended_window_from_monthly_archives(tmp_path) -> None:
    """Restore older retained samples when upgrading from a shorter rolling file.

    Duplicate archive and rolling observations must not become duplicate rows.
    """
    path = tmp_path / "history.csv"
    repository = CsvHistoryRepository(path)
    now = datetime(2026, 10, 30, 12, tzinfo=UTC)
    old = observation(now - timedelta(days=36), 100)
    recent = observation(now - timedelta(days=2), 200)
    repository.append(tmp_path / "history-2026-09.csv", old)
    repository.append(tmp_path / "history-2026-10.csv", recent)
    repository.append(path, recent)

    points = repository.save(observation(now, 300))

    assert [point.bars_sold for point in points] == [100, 200, 300]
    assert repository.read() == points
    assert repository.read(tmp_path / "history-2026-09.csv") == [old]


def test_archive_survives_cache_failure_and_restores_on_next_poll(tmp_path, monkeypatch) -> None:
    """Keep the full observation when the rolling cache cannot be updated.

    A later poll must rebuild the cache from the durable monthly archive.
    """
    path = tmp_path / "history.csv"
    repository = CsvHistoryRepository(path)
    original_append = repository.append
    first = observation(datetime(2026, 10, 30, 12, tzinfo=UTC), 100)
    second = observation(datetime(2026, 10, 30, 12, 1, tzinfo=UTC), 101)

    def fail_cache(target, point) -> None:
        """Simulate a cache write failure while allowing archive writes.

        Preserve the production archive writer for all other paths.
        """
        if target == path:
            raise OSError("cache unavailable")
        original_append(target, point)

    monkeypatch.setattr(repository, "append", fail_cache)
    with pytest.raises(OSError, match="cache unavailable"):
        repository.save(first)

    assert repository.read(tmp_path / "history-2026-10.csv") == [first]
    monkeypatch.setattr(repository, "append", original_append)
    assert repository.save(second) == [first, second]
    assert repository.read(tmp_path / "history-2026-10.csv") == [first, second]


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


def test_display_publisher_writes_latest_daily_observation_to_current_csv(tmp_path) -> None:
    """Publish the newest daily sample even when observations are unordered.

    A falling count remains visible instead of being replaced by the largest count.
    """
    path = tmp_path / "public" / "history.csv"
    publisher = DisplayHistoryCsvPublisher(path, "UTC")
    older = observation(datetime(2026, 10, 30, 10, 5, tzinfo=UTC), 510)
    latest = observation(datetime(2026, 10, 30, 10, 55, tzinfo=UTC), 500)

    publisher.publish([latest, older])

    current_path = path.with_name("current.csv")
    assert read_compact(current_path) == [latest]
    assert not current_path.with_name(".current.csv.tmp").exists()
    assert CsvHistoryRepository(path).read() == [latest]


def test_compact_feeds_omit_source_timestamp_without_changing_archive(tmp_path) -> None:
    """Keep the source timestamp in durable history but omit it from public feeds.

    The legacy public history stays compatible with older application versions.
    """
    at = datetime(2026, 10, 30, 12, tzinfo=UTC)
    point = SalesObservation(observed_at=at, bars_sold=500, source_updated_at=at - timedelta(minutes=5))
    archive = tmp_path / "history.csv"
    repository = CsvHistoryRepository(archive)
    points = repository.save(point)
    public = tmp_path / "public" / "history.csv"

    DisplayHistoryCsvPublisher(public, "UTC").publish(points)

    assert repository.read(tmp_path / "history-2026-10.csv") == [point]
    assert CsvHistoryRepository(public).read() == [point]
    assert read_compact(public.with_name("current.csv")) == [observation(at, 500)]
    assert read_compact(public.with_name("older.csv")) == []


def test_current_csv_keeps_eight_local_days_and_a_previous_day_anchor(tmp_path) -> None:
    """Keep daily endpoints and the preceding anchor for the eight-day chart.

    Boundaries follow the configured timezone, and current day uses the latest sample.
    """
    path = tmp_path / "history.csv"
    publisher = DisplayHistoryCsvPublisher(path, "Europe/Moscow")
    start = datetime(2026, 10, 20, 21, 30, tzinfo=UTC)
    points = [
        observation(start + timedelta(hours=hour), 1000 + hour)
        for hour in range(10 * 24 + 1)
    ]

    publisher.publish(list(reversed(points)))

    current = read_compact(path.with_name("current.csv"))
    assert len(current) == 9
    assert current[0].observed_at == datetime(2026, 10, 23, 20, 30, tzinfo=UTC)
    assert current[-1] == points[-1]
    assert all(a.observed_at < b.observed_at for a, b in zip(current, current[1:]))


def test_older_csv_combines_with_current_into_36_days(tmp_path) -> None:
    """Publish 28 older days plus an anchor and overlap at the join.

    Combining and deduplicating both files yields 36 days with a prior anchor.
    """
    path = tmp_path / "history.csv"
    publisher = DisplayHistoryCsvPublisher(path, "UTC")
    start = datetime(2026, 9, 16, 12, tzinfo=UTC)
    points = [
        observation(start + timedelta(days=day), 1000 + day)
        for day in range(45)
    ]

    publisher.publish(points)

    older = read_compact(path.with_name("older.csv"))
    current = read_compact(path.with_name("current.csv"))
    assert len(older) == 29
    assert len(current) == 9
    assert older[0].observed_at.date().isoformat() == "2026-09-24"
    assert older[-1] == current[0]
    combined = {point.observed_at: point for point in older + current}
    assert len(combined) == 37
    assert max(combined) == points[-1].observed_at


def test_display_publisher_clears_current_csv_when_history_is_empty(tmp_path) -> None:
    """Publish an empty, valid CSV instead of leaving an obsolete count visible.

    Both the legacy projection and the current snapshot keep their schema.
    """
    path = tmp_path / "history.csv"
    publisher = DisplayHistoryCsvPublisher(path, "UTC")
    publisher.publish([observation(datetime(2026, 10, 30, 10, tzinfo=UTC), 5)])

    publisher.publish([])

    assert read_compact(path.with_name("current.csv")) == []
    assert read_compact(path.with_name("older.csv")) == []
    assert CsvHistoryRepository(path).read() == []


def test_display_publisher_rejects_colliding_paths(tmp_path) -> None:
    """Reject a configuration that would overwrite the legacy history projection.

    The current snapshot and historical series must be separate files.
    """
    with pytest.raises(ValueError, match="paths must differ"):
        DisplayHistoryCsvPublisher(tmp_path / "current.csv", "UTC")
    with pytest.raises(ValueError, match="paths must differ"):
        DisplayHistoryCsvPublisher(tmp_path / "older.csv", "UTC")
