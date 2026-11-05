"""SQLite-backed cumulative sales index for calendar projections."""

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from busy_profit.models import SalesObservation


class ObservationIndex:
    """Store observations separately from immutable source CSV archives."""

    def __init__(self, path: Path) -> None:
        """Create the index and its timestamp lookup table.

        Open short-lived connections so request handling never shares cursors.
        """
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE IF NOT EXISTS observations (at INTEGER PRIMARY KEY, count INTEGER NOT NULL CHECK(count>=0))")
            connection.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL)")
            connection.execute("INSERT OR IGNORE INTO state VALUES (1,0)")
            for action in ["INSERT", "UPDATE", "DELETE"]:
                connection.execute(f"CREATE TRIGGER IF NOT EXISTS revision_{action} AFTER {action} ON observations BEGIN UPDATE state SET revision=revision+1 WHERE id=1; END")

    def import_points(self, points: list[SalesObservation]) -> None:
        """Upsert a batch atomically, preserving corrected source totals.

        Reimporting identical observations does not change their meaning.
        """
        with sqlite3.connect(self._path) as connection:
            connection.executemany(
                "INSERT INTO observations VALUES (?, ?) ON CONFLICT(at) DO UPDATE SET count=excluded.count WHERE count!=excluded.count",
                [(int(point.observed_at.timestamp()), point.bars_sold) for point in points],
            )

    def close(self, boundary: datetime, maximum_gap: int = 7200) -> int | None:
        """Find the last known cumulative count before a calendar boundary.

        Missing or stale coverage is unknown, never an inferred zero.
        """
        at = int(boundary.astimezone(UTC).timestamp())
        with sqlite3.connect(self._path) as connection:
            row = connection.execute(
                "SELECT at,count FROM observations WHERE at<? ORDER BY at DESC LIMIT 1",
                (at,),
            ).fetchone()
        return row[1] if row and at - row[0] <= maximum_gap else None

    @contextmanager
    def snapshot(self) -> Iterator["ReadSnapshot"]:
        """Hold one consistent read transaction for revision and projection.

        Concurrent imports cannot mix data from different revisions in a response.
        """
        with sqlite3.connect(self._path) as connection:
            connection.execute("BEGIN")
            yield ReadSnapshot(connection)


class ReadSnapshot:
    """Expose calendar lookups within an existing read transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Capture revision and latest count from the transaction.

        Empty databases have a valid zero revision and total.
        """
        self._connection = connection
        self.revision = str(connection.execute("SELECT revision FROM state WHERE id=1").fetchone()[0])
        row = connection.execute("SELECT count FROM observations ORDER BY at DESC LIMIT 1").fetchone()
        self.total = row[0] if row else 0

    def close(self, boundary: datetime, maximum_gap: int = 7200) -> int | None:
        """Look up a covered close without opening additional connections.

        Preserve the same missing-data rule as the repository.
        """
        at = int(boundary.timestamp())
        row = self._connection.execute("SELECT at,count FROM observations WHERE at<? ORDER BY at DESC LIMIT 1", (at,)).fetchone()
        return row[1] if row and at - row[0] <= maximum_gap else None
