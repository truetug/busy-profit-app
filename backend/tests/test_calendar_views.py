"""Regression coverage for calendar boundaries and indexed source coverage."""

from datetime import UTC, date, datetime, timedelta

from busy_profit.calendar_views import daily_values, hourly_values
from busy_profit.models import SalesObservation
from busy_profit.view_storage import ObservationIndex


def test_dst_days_preserve_all_real_hours(tmp_path) -> None:
    """Verify Berlin spring and autumn days without losing repeated hours.

    A constant one-sale-per-hour source makes the duration observable.
    """
    index = ObservationIndex(tmp_path / "views.sqlite3")
    for day, duration in [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)]:
        origin = datetime.combine(day - timedelta(days=1), datetime.min.time(), UTC)
        points = []
        for hour in range(75):
            at = origin + timedelta(hours=hour, minutes=59)
            points.append(SalesObservation(observed_at=at, source_updated_at=at, bars_sold=hour))
        index.import_points(points)
        starts, values = hourly_values(index, day, "Europe/Berlin")
        assert len(starts) == duration
        assert values == [1] * duration
        assert daily_values(index, day, 1, "Europe/Berlin") == [duration]


def test_missing_coverage_and_correction_are_unknown(tmp_path) -> None:
    """Do not fabricate sales from sparse or decreasing cumulative counts.

    Fresh equal totals still represent a genuine zero.
    """
    index = ObservationIndex(tmp_path / "views.sqlite3")
    points = []
    for day, count in [(1, 100), (2, 100), (3, 99)]:
        at = datetime(2026, 9, day, 23, 59, tzinfo=UTC)
        points.append(SalesObservation(observed_at=at, source_updated_at=at, bars_sold=count))
    index.import_points(points)
    assert daily_values(index, date(2026, 9, 2), 3, "UTC") == [0, None, None]
    assert index.close(datetime(2026, 9, 8, tzinfo=UTC)) is None
