"""Check privacy and denominators for employee activity aggregates."""

from datetime import UTC, datetime, timedelta

from busy_profit.usage_events import UsageEvents


def test_issuance_does_not_count_as_use_and_reports_are_separate(tmp_path) -> None:
    """Count active people, not PIN requests or shared credentials.

    Delivered report totals are independent of the unique employee count.
    """
    events = UsageEvents(tmp_path / "activity.sqlite3")
    now = datetime(2026, 11, 5, 12, tzinfo=UTC)
    events.record("employee", "T:issued-only", "pin_issued", now)
    events.record("employee", "T:returning", "data_read", now-timedelta(days=9))
    events.record("employee", "T:returning", "slack_day", now)
    events.record("employee", "T:new", "slack_month", now)
    events.record("shared", "system:shared", "data_read", now)
    summary = events.summary(now)
    assert summary["active_employees"] == 2
    assert summary["new_employees"] == 1
    assert summary["returning_employees"] == 1
    assert summary["day_reports"] == summary["month_reports"] == 1
    assert "T:new" not in str(summary)
