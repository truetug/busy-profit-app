"""Exercise usage parsing, incremental imports, rotation, retention and IP history."""

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from busy_profit.usage_application import import_usage_logs
from busy_profit.usage_parser import parse_usage_line
from busy_profit.usage_storage import UsageRepository

UID = "203638485431500400ABCDEF"
NOW = datetime(2026, 11, 3, tzinfo=UTC)


def entry(at: datetime = NOW, ip: str = "192.0.2.1", uid: str = UID, status: int = 200) -> bytes:
    """Build a representative access record with deliberately untrusted headers.

    The parser must use the peer address rather than the spoofed forwarded value.
    """
    return (json.dumps({"ts": at.timestamp(), "status": status, "request": {
        "method": "GET", "uri": "/current.csv", "remote_ip": ip,
        "headers": {"X-Busy-Hardware-Id": [uid], "X-Forwarded-For": ["198.51.100.99"], "Authorization": ["REDACTED"]},
    }}) + "\n").encode()


def query(path: Path, sql: str) -> list[tuple]:
    """Read persisted output using an independent connection.

    This also verifies that each completed import transaction is visible on disk.
    """
    with sqlite3.connect(path) as connection:
        return connection.execute(sql).fetchall()


def test_parser_uses_peer_ip_and_normalizes_uid() -> None:
    """Trust neither arbitrary forwarding headers nor malformed device metadata.

    Keep anonymous requests useful for error counters without creating devices.
    """
    event = parse_usage_line(entry(uid=UID.lower()))
    assert event is not None
    assert event.hardware_id == UID
    assert str(event.ip) == "192.0.2.1"
    assert parse_usage_line(entry(uid="bad")).hardware_id == ""
    assert parse_usage_line(entry(ip="not-an-ip")) is None
    assert parse_usage_line(b"invalid\n") is None
    assert parse_usage_line(b"[]\n") is None


def test_import_is_idempotent_and_tracks_ip_transitions(tmp_path: Path) -> None:
    """Track new devices, hourly endpoint counts and actual chronological IP changes.

    Re-reading committed files must never double count requests or transitions.
    """
    path = tmp_path / "usage.sqlite3"
    log = tmp_path / "busy-profit-access.json"
    log.write_bytes(entry() + entry(NOW + timedelta(minutes=1), "2001:db8::1") + entry(NOW + timedelta(minutes=2), "192.0.2.1"))
    repo = UsageRepository(path)
    assert import_usage_logs(tmp_path, repo) == 3
    assert import_usage_logs(tmp_path, repo) == 0
    repo.close()
    assert query(path, "SELECT count FROM usage_hourly") == [(3,)]
    assert query(path, "SELECT count(*) FROM devices") == [(1,)]
    assert query(path, "SELECT previous_ip, ip FROM ip_changes ORDER BY id") == [(None, "192.0.2.1"), ("192.0.2.1", "2001:db8::1"), ("2001:db8::1", "192.0.2.1")]
    assert query(path, "SELECT sum(count) FROM device_ips") == [(3,)]


def test_rotation_restart_and_partial_tail(tmp_path: Path) -> None:
    """Follow uncompressed renamed files and defer incomplete records until complete.

    Persist the cursor across a worker restart and ignore malformed complete lines.
    """
    db = tmp_path / "usage.sqlite3"
    log = tmp_path / "busy-profit-access.json"
    record = entry()
    log.write_bytes(record + b"malformed\n" + record[:20])
    repo = UsageRepository(db)
    assert import_usage_logs(tmp_path, repo) == 1
    repo.close()
    with log.open("ab") as stream:
        stream.write(record[20:])
    log.rename(tmp_path / "busy-profit-access-rotated.json")
    log.write_bytes(entry(NOW + timedelta(hours=1)))
    repo = UsageRepository(db)
    assert import_usage_logs(tmp_path, repo) == 2
    assert import_usage_logs(tmp_path, repo) == 0
    repo.close()
    assert query(db, "SELECT sum(count) FROM usage_hourly") == [(3,)]


def test_transaction_failure_rolls_back_events_and_cursor(tmp_path: Path) -> None:
    """Retry a failed batch without retaining partially accumulated usage.

    An injected SQLite constraint failure represents an interrupted persistence step.
    """
    db = tmp_path / "usage.sqlite3"
    repo = UsageRepository(db)
    event = parse_usage_line(entry())
    assert event is not None
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TRIGGER reject_cursor BEFORE INSERT ON log_cursors BEGIN SELECT RAISE(ABORT, 'failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        repo.commit_batch("file", 100, [event])
    assert repo.offset("file") == 0
    assert query(db, "SELECT count(*) FROM devices") == [(0,)]
    repo.close()


def test_retention_and_late_records_do_not_undo_current_ip(tmp_path: Path) -> None:
    """Keep the newest IP when late logs arrive and prune detailed old history.

    Device first-seen metadata remains available after the detail retention window.
    """
    db = tmp_path / "usage.sqlite3"
    repo = UsageRepository(db)
    events = [parse_usage_line(entry()), parse_usage_line(entry(NOW - timedelta(days=100), "192.0.2.2"))]
    repo.commit_batch("file", 100, [event for event in events if event is not None])
    assert query(db, "SELECT last_ip FROM devices") == [("192.0.2.1",)]
    repo.prune(NOW, 90)
    repo.close()
    assert query(db, "SELECT count(*) FROM devices") == [(1,)]
    assert query(db, "SELECT sum(count) FROM usage_hourly") == [(1,)]
    assert query(db, "SELECT count(*) FROM device_ips") == [(1,)]


def test_anonymous_failures_do_not_create_devices(tmp_path: Path) -> None:
    """Count rejected requests without mistaking missing UIDs for real devices.

    HTTP status remains a dimension so legitimate usage can exclude failed PINs.
    """
    db = tmp_path / "usage.sqlite3"
    repo = UsageRepository(db)
    event = parse_usage_line(entry(uid="", status=401))
    assert event is not None
    repo.commit_batch("file", 10, [event])
    repo.close()
    assert query(db, "SELECT hardware_id, status, count FROM usage_hourly") == [("", 401, 1)]
    assert query(db, "SELECT count(*) FROM devices") == [(0,)]
