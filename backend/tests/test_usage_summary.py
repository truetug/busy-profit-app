"""Verify public metrics and rendering without publishing private identities."""

from datetime import timedelta
from pathlib import Path
from xml.etree import ElementTree

from functools import partial

from busy_profit.analytics import LABELS
from request_analytics import publish_usage_infographic as publish, render_usage_svg as render
from test_usage import NOW, UID, entry, parse_usage_line, UsageRepository

publish_usage_infographic = partial(publish, labels=LABELS)
render_usage_svg = partial(render, labels=LABELS)


def test_session_maxima_are_idempotent_and_ignore_old_snapshots(tmp_path: Path) -> None:
    """Count starts once and derive time and detail increments from session maxima.

    Repeated or reordered successful polls cannot inflate public engagement metrics.
    """
    repository = UsageRepository(tmp_path / "usage.sqlite3")
    event = parse_usage_line(entry())
    assert event is not None
    for index, (seconds, details) in enumerate([(60, 1), (120, 2), (120, 2), (30, 0)]):
        snapshot = event.model_copy(update={"session_id": "session-123", "uptime_seconds": seconds, "details_count": details})
        repository.commit_batch("test", index, [snapshot])
    summary = repository.weekly_summary(NOW)
    assert (summary.starts, summary.runtime_seconds, summary.details) == (1, 120, 2)
    assert summary.active == summary.new == 1
    assert summary.regular == summary.returning == 0
    assert summary.days[0].active is None
    assert summary.days[-1].active == 1
    for mobile in [False, True]:
        svg = render_usage_svg(summary, mobile)
        ElementTree.fromstring(svg)
        assert UID not in svg
        assert "192.0.2.1" not in svg
        assert "Updated 03 Nov 2026" in svg
    publish_usage_infographic(summary, tmp_path / "public")
    assert (tmp_path / "public/usage.svg").exists()
    assert (tmp_path / "public/usage-mobile.svg").exists()
    repository.close()


def test_returning_regular_and_new_bars_have_explicit_definitions(tmp_path: Path) -> None:
    """Partition weekly activity into new and returning devices and count active days.

    Regular usage overlaps that partition and requires three distinct UTC days.
    """
    repository = UsageRepository(tmp_path / "usage.sqlite3")
    events = [parse_usage_line(entry(NOW - timedelta(days=days))) for days in [10, 2, 1, 0]]
    events.append(parse_usage_line(entry(uid="203638485431500400123456")))
    repository.commit_batch("test", 100, [event for event in events if event is not None])
    summary = repository.weekly_summary(NOW)
    assert (summary.active, summary.new, summary.returning, summary.regular) == (2, 1, 1, 1)
    assert summary.starts is summary.details is summary.runtime_seconds is None
    assert [day.active for day in summary.days] == [0, 0, 0, 0, 1, 1, 2]
    repository.close()


def test_parser_keeps_usage_when_session_metadata_is_invalid() -> None:
    """Reject malformed telemetry independently of otherwise valid feed requests.

    Old clients without the new headers continue contributing device activity.
    """
    import json

    record = json.loads(entry())
    record["request"]["headers"].update({"X-Busy-Session-ID": ["session-123"], "X-Busy-Uptime-Seconds": ["bad"]})
    event = parse_usage_line(json.dumps(record).encode())
    assert event is not None
    assert event.session_id == ""
