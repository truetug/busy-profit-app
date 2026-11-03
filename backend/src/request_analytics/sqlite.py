"""Persist private usage aggregates and file checkpoints atomically in SQLite."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from request_analytics.models import UsageDay, UsageEvent, UsageSummary

SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
 hardware_id TEXT PRIMARY KEY, first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, last_ip TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage_hourly (
 hour TEXT NOT NULL, hardware_id TEXT NOT NULL, endpoint TEXT NOT NULL,
 status INTEGER NOT NULL, count INTEGER NOT NULL,
 PRIMARY KEY(hour, hardware_id, endpoint, status));
CREATE TABLE IF NOT EXISTS device_ips (
 hardware_id TEXT NOT NULL, ip TEXT NOT NULL, first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, count INTEGER NOT NULL,
 PRIMARY KEY(hardware_id, ip));
CREATE TABLE IF NOT EXISTS ip_changes (
 id INTEGER PRIMARY KEY, hardware_id TEXT NOT NULL, observed_at TEXT NOT NULL,
 previous_ip TEXT, ip TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ip_changes_device_time ON ip_changes(hardware_id, observed_at);
CREATE TABLE IF NOT EXISTS log_cursors (
 file_id TEXT PRIMARY KEY, offset INTEGER NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS usage_sessions (
 hardware_id TEXT NOT NULL, session_id TEXT NOT NULL, first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, uptime_seconds INTEGER NOT NULL, details_count INTEGER NOT NULL,
 PRIMARY KEY(hardware_id, session_id));
CREATE TABLE IF NOT EXISTS usage_daily (
 day TEXT NOT NULL, hardware_id TEXT NOT NULL, starts INTEGER NOT NULL,
 runtime_seconds INTEGER NOT NULL, details_count INTEGER NOT NULL,
 PRIMARY KEY(day, hardware_id));
"""


class UsageRepository:
    """Own SQLite connections and commit usage rows together with checkpoints."""

    def __init__(self, path: Path, session_endpoint: str) -> None:
        """Initialize a private local database with crash-safe WAL journaling.

        Keep all analytics outside the directory served by the web server.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        self._session_endpoint = session_endpoint
        self._db = sqlite3.connect(path, timeout=30)
        path.chmod(0o600)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)

    def offset(self, file_id: str) -> int:
        """Return the last committed complete-record position for a file inode.

        Unknown files start at zero, including newly rotated active logs.
        """
        row = self._db.execute("SELECT offset FROM log_cursors WHERE file_id=?", (file_id,)).fetchone()
        return row[0] if row else 0

    def commit_batch(self, file_id: str, offset: int, events: list[UsageEvent]) -> None:
        """Update all aggregates and the reader cursor in a single transaction.

        A failed transaction can be retried without double counting any request.
        """
        with self._db:
            for event in events:
                self._record(event)
            self._db.execute(
                "INSERT INTO log_cursors VALUES (?, ?, ?) ON CONFLICT(file_id) DO UPDATE SET offset=excluded.offset, updated_at=excluded.updated_at",
                (file_id, offset, datetime.now(UTC).isoformat()),
            )

    def _record(self, event: UsageEvent) -> None:
        """Accumulate endpoint usage and maintain chronologically ordered IP changes.

        Late records update first-seen counts but never roll back the current IP.
        """
        at = event.at.isoformat()
        hour = event.at.replace(minute=0, second=0, microsecond=0).isoformat()
        uid, ip = event.hardware_id, str(event.ip)
        self._db.execute(
            "INSERT INTO usage_hourly VALUES (?, ?, ?, ?, 1) ON CONFLICT(hour, hardware_id, endpoint, status) DO UPDATE SET count=count+1",
            (hour, uid, event.endpoint, event.status),
        )
        if not uid:
            return
        if event.status == 200 and event.endpoint == self._session_endpoint and event.session_id:
            self._record_session(event)
        previous = self._db.execute("SELECT last_seen_at, last_ip FROM devices WHERE hardware_id=?", (uid,)).fetchone()
        if previous is None or (at >= previous[0] and ip != previous[1]):
            self._db.execute("INSERT INTO ip_changes(hardware_id, observed_at, previous_ip, ip) VALUES (?, ?, ?, ?)", (uid, at, previous[1] if previous else None, ip))
        self._db.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?) ON CONFLICT(hardware_id) DO UPDATE SET first_seen_at=min(first_seen_at, excluded.first_seen_at), last_ip=CASE WHEN excluded.last_seen_at >= last_seen_at THEN excluded.last_ip ELSE last_ip END, last_seen_at=max(last_seen_at, excluded.last_seen_at)",
            (uid, at, at, ip),
        )
        self._db.execute(
            "INSERT INTO device_ips VALUES (?, ?, ?, ?, 1) ON CONFLICT(hardware_id, ip) DO UPDATE SET first_seen_at=min(first_seen_at, excluded.first_seen_at), last_seen_at=max(last_seen_at, excluded.last_seen_at), count=count+1",
            (uid, ip, at, at),
        )

    def _record_session(self, event: UsageEvent) -> None:
        """Convert cumulative counters to nonnegative increments exactly once.

        Old or repeated snapshots cannot add runtime or detail opens again.
        """
        previous = self._db.execute("SELECT uptime_seconds, details_count FROM usage_sessions WHERE hardware_id=? AND session_id=?", (event.hardware_id, event.session_id)).fetchone()
        runtime = max(0, event.uptime_seconds - (previous[0] if previous else 0))
        details = max(0, event.details_count - (previous[1] if previous else 0))
        at = event.at.isoformat()
        self._db.execute("INSERT INTO usage_sessions VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(hardware_id, session_id) DO UPDATE SET last_seen_at=max(last_seen_at, excluded.last_seen_at), uptime_seconds=max(uptime_seconds, excluded.uptime_seconds), details_count=max(details_count, excluded.details_count)", (event.hardware_id, event.session_id, at, at, event.uptime_seconds, event.details_count))
        self._db.execute("INSERT INTO usage_daily VALUES (?, ?, ?, ?, ?) ON CONFLICT(day, hardware_id) DO UPDATE SET starts=starts+excluded.starts, runtime_seconds=runtime_seconds+excluded.runtime_seconds, details_count=details_count+excluded.details_count", (event.at.date().isoformat(), event.hardware_id, int(previous is None), runtime, details))

    def prune(self, now: datetime, retention_days: int) -> None:
        """Bound detailed usage and IP retention while preserving device first-seen.

        Keep recent file checkpoints longer than the seven-day log retention.
        """
        cutoff = (now - timedelta(days=retention_days)).isoformat()
        with self._db:
            for table, column in (("usage_hourly", "hour"), ("device_ips", "last_seen_at"), ("ip_changes", "observed_at"), ("log_cursors", "updated_at"), ("usage_sessions", "last_seen_at"), ("usage_daily", "day")):
                self._db.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))

    def weekly_summary(self, now: datetime) -> UsageSummary:
        """Calculate seven UTC calendar days of successful identified usage.

        Keep pre-collection days and unavailable session metrics explicitly missing.
        """
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        rows = self._db.execute("SELECT hardware_id, substr(hour,1,10), sum(count) FROM usage_hourly WHERE status=200 AND hardware_id != '' AND hour >= ? AND hour <= ? GROUP BY hardware_id, substr(hour,1,10)", (start.isoformat(), now.isoformat())).fetchall()
        devices: dict[str, set[str]] = {}
        daily: dict[str, set[str]] = {}
        for uid, day, _ in rows:
            devices.setdefault(uid, set()).add(day)
            daily.setdefault(day, set()).add(uid)
        first_seen = dict(self._db.execute("SELECT hardware_id, first_seen_at FROM devices"))
        new = sum(first_seen[uid] >= start.isoformat() for uid in devices)
        coverage = self._db.execute("SELECT min(hour) FROM usage_hourly WHERE hardware_id != '' AND status=200").fetchone()[0]
        telemetry = self._db.execute("SELECT min(first_seen_at) FROM usage_sessions").fetchone()[0]
        starts, runtime, details = self._db.execute("SELECT coalesce(sum(starts),0),coalesce(sum(runtime_seconds),0),coalesce(sum(details_count),0) FROM usage_daily WHERE day >= ? AND day <= ?", (start.date().isoformat(), now.date().isoformat())).fetchone()
        days = []
        for offset in range(7):
            day = (start + timedelta(days=offset)).date()
            days.append(UsageDay(day=day, active=len(daily.get(day.isoformat(), set())) if coverage and day.isoformat() >= coverage[:10] else None))
        return UsageSummary(generated_at=now, active=len(devices), new=new, returning=len(devices)-new, regular=sum(len(days) >= 3 for days in devices.values()), starts=starts if telemetry else None, details=details if telemetry else None, runtime_seconds=runtime if telemetry else None, session_since=datetime.fromisoformat(telemetry) if telemetry else None, days=days)

    def close(self) -> None:
        """Close the connection after an import or a clean worker shutdown.

        Transactions are already committed by each completed batch.
        """
        self._db.close()
