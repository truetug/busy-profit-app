"""Persist private usage aggregates and file checkpoints atomically in SQLite."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from busy_profit.usage_models import UsageEvent

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
"""


class UsageRepository:
    """Own SQLite connections and commit usage rows together with checkpoints."""

    def __init__(self, path: Path) -> None:
        """Initialize a private local database with crash-safe WAL journaling.

        Keep all analytics outside the directory served by the web server.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def prune(self, now: datetime, retention_days: int) -> None:
        """Bound detailed usage and IP retention while preserving device first-seen.

        Keep recent file checkpoints longer than the seven-day log retention.
        """
        cutoff = (now - timedelta(days=retention_days)).isoformat()
        with self._db:
            for table, column in (("usage_hourly", "hour"), ("device_ips", "last_seen_at"), ("ip_changes", "observed_at"), ("log_cursors", "updated_at")):
                self._db.execute(f"DELETE FROM {table} WHERE {column} < ?", (cutoff,))

    def close(self) -> None:
        """Close the connection after an import or a clean worker shutdown.

        Transactions are already committed by each completed batch.
        """
        self._db.close()
