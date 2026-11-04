"""Publish compact, static UTC monthly sales feeds."""

import json
import os
import re
from datetime import UTC, date, datetime, time
from pathlib import Path

from busy_profit.csv_storage import CsvHistoryRepository
from busy_profit.models import SalesObservation
from busy_profit.monthly_projection import hourly_utc_snapshots


class MonthlyArchivePublisher:
    """Refresh the current month and rebuild older months only on source changes."""

    def __init__(self, history_path: Path, public_path: Path) -> None:
        """Bind the private source and public archive directories.

        Track source signatures in memory for the lifetime of the collector.
        """
        self._history = history_path
        self._repository = CsvHistoryRepository(history_path)
        self._output = public_path.parent / "archive"
        self._cache: dict[str, tuple[tuple[int, int, date | None, datetime | None, int | None], SalesObservation | None]] = {}

    def _publish(self, filename: str, content: str) -> None:
        """Atomically replace a static file only when its bytes change.

        Existing unchanged files retain their modification time across restarts.
        """
        self._output.mkdir(parents=True, exist_ok=True)
        target = self._output / filename
        if target.exists() and target.read_text(encoding="utf-8") == content:
            return
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, target)

    def refresh(self, now: datetime) -> None:
        """Publish completed UTC days, then make their month index visible.

        Include the most recent prior observation as a cross-month anchor.
        """
        today = now.astimezone(UTC).date()
        cutoff = datetime.combine(today, time.min, UTC)
        previous: SalesObservation | None = None
        months: list[str] = []
        for source in sorted(self._history.parent.glob(f"{self._history.stem}-*{self._history.suffix}")):
            month = source.stem.removeprefix(self._history.stem + "-")
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month) or month > today.strftime("%Y-%m"):
                continue
            stat = source.stat()
            active = month == today.strftime("%Y-%m")
            signature = (
                stat.st_mtime_ns if not active else 0,
                stat.st_size if not active else 0,
                today if active else None,
                previous.observed_at if previous else None,
                previous.bars_sold if previous else None,
            )
            cached = self._cache.get(month)
            if cached and cached[0] == signature:
                if cached[1] is not None:
                    previous = cached[1]
                    months.append(month)
                continue
            points = hourly_utc_snapshots(self._repository.read(source), cutoff)
            if points:
                rows = ([previous] if previous is not None else []) + points
                content = "observed_at,bars_sold\n" + "".join(
                    f"{point.observed_at.isoformat()},{point.bars_sold}\n"
                    for point in rows
                )
                self._publish(f"{month}.csv", content)
                previous = points[-1]
                months.append(month)
            self._cache[month] = (signature, points[-1] if points else None)
        self._publish("index.json", json.dumps({"months": months}) + "\n")
