"""CSV repositories and hourly projection publisher for sales history."""

import csv
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from busy_profit.models import SalesObservation

FIELDNAMES = ("observed_at", "bars_sold", "source_updated_at")
ROLLING_DAYS = 38


def csv_row(point: SalesObservation) -> dict[str, str | int]:
    """Map a typed observation into the stable flat CSV row schema."""
    return {
        "observed_at": point.observed_at.isoformat(),
        "bars_sold": point.bars_sold,
        "source_updated_at": point.source_updated_at.isoformat(),
    }


class CsvHistoryRepository:
    """Keep complete monthly history and a bounded rolling cache as CSV files."""

    def __init__(self, path: Path) -> None:
        """Set the root rolling-history path used to derive monthly archive names."""
        self._path = path
        self._bootstrapped = False

    def read(self, path: Path | None = None) -> list[SalesObservation]:
        """Load and validate observations, treating only a missing file as empty."""
        target = path or self._path
        if not target.exists():
            return []
        with target.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != FIELDNAMES:
                raise ValueError(f"invalid sales history CSV header: {target}")
            points = [SalesObservation.model_validate(row) for row in reader]
        return sorted(points, key=lambda point: point.observed_at)

    def append(self, path: Path, point: SalesObservation) -> None:
        """Append and flush one row, creating its header when the file is empty."""
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow(csv_row(point))
            stream.flush()
            os.fsync(stream.fileno())

    def rewrite(self, path: Path, points: list[SalesObservation]) -> None:
        """Atomically replace a CSV file with the supplied validated observations."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(csv_row(point) for point in points)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def save(self, point: SalesObservation) -> list[SalesObservation]:
        """Persist each observation in its monthly archive before updating the cache.

        Restore the rolling window from archives on startup or after a cache failure.
        """
        cutoff = point.observed_at - timedelta(days=ROLLING_DAYS)
        monthly_path = self._path.with_name(
            f"{self._path.stem}-{point.observed_at:%Y-%m}{self._path.suffix}",
        )
        self.append(monthly_path, point)
        try:
            existing = self.read()
            if not self._bootstrapped:
                restored = {item.observed_at: item for item in existing}
                month = cutoff.replace(day=1)
                while month <= point.observed_at:
                    archive = self._path.with_name(
                        f"{self._path.stem}-{month:%Y-%m}{self._path.suffix}",
                    )
                    for item in self.read(archive):
                        if cutoff <= item.observed_at < point.observed_at:
                            restored.setdefault(item.observed_at, item)
                    month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
                existing = sorted(restored.values(), key=lambda item: item.observed_at)
            retained = [item for item in existing if item.observed_at >= cutoff]
            crossed_day = (
                bool(existing)
                and existing[-1].observed_at.date() != point.observed_at.date()
            )
            if not self._bootstrapped or len(retained) != len(existing) or crossed_day:
                self.rewrite(self._path, retained)
            self.append(self._path, point)
            self._bootstrapped = True
            return [item for item in self.read() if item.observed_at >= cutoff]
        except Exception:
            self._bootstrapped = False
            raise


class DisplayHistoryCsvPublisher:
    """Publish legacy history and a compact eight-day display projection."""

    def __init__(self, path: Path, timezone_name: str) -> None:
        """Configure separate history and current projection destinations.

        Keep day boundaries aligned to the display timezone.
        """
        self._path = path
        self._current_path = path.with_name("current.csv")
        self._older_path = path.with_name("older.csv")
        if len({self._path, self._current_path, self._older_path}) != 3:
            raise ValueError("display history and current CSV paths must differ")
        self._timezone = ZoneInfo(timezone_name)

    def publish(self, points: list[SalesObservation]) -> None:
        """Publish the legacy projection and eight recent days separately.

        Replace each CSV atomically while preserving recent hourly detail.
        """
        by_hour: dict[datetime, SalesObservation] = {}
        by_day: dict[date, SalesObservation] = {}
        for point in points:
            local_time = point.observed_at.astimezone(self._timezone)
            hour = local_time.replace(minute=0, second=0, microsecond=0)
            if hour not in by_hour or point.observed_at > by_hour[hour].observed_at:
                by_hour[hour] = point
            day = local_time.date()
            if day not in by_day or point.observed_at > by_day[day].observed_at:
                by_day[day] = point

        if not by_hour:
            CsvHistoryRepository(self._path).rewrite(self._path, [])
            CsvHistoryRepository(self._current_path).rewrite(self._current_path, [])
            CsvHistoryRepository(self._older_path).rewrite(self._older_path, [])
            return

        latest_hour = max(by_hour)
        recent_start = latest_hour - timedelta(hours=48)
        recent_hours = [
            point
            for hour, point in by_hour.items()
            if hour >= recent_start
        ]
        older_daily = [
            point
            for day, point in by_day.items()
            if day < recent_start.date()
        ]
        projection = {point.observed_at: point for point in older_daily + recent_hours}
        CsvHistoryRepository(self._path).rewrite(
            self._path,
            sorted(projection.values(), key=lambda item: item.observed_at),
        )
        latest = max(points, key=lambda point: point.observed_at)
        start_day = latest.observed_at.astimezone(self._timezone).date() - timedelta(days=7)
        earlier = [
            point
            for day, point in by_day.items()
            if day < start_day
        ]
        recent = [
            point
            for day, point in by_day.items()
            if day >= start_day
        ]
        if earlier:
            recent.append(max(earlier, key=lambda point: point.observed_at))
        CsvHistoryRepository(self._current_path).rewrite(
            self._current_path,
            sorted(recent, key=lambda point: point.observed_at),
        )
        oldest_day = start_day - timedelta(days=28)
        older = [
            point
            for day, point in by_day.items()
            if oldest_day <= day < start_day
        ]
        anchors = [
            point
            for day, point in by_day.items()
            if day < oldest_day
        ]
        if anchors:
            older.append(max(anchors, key=lambda point: point.observed_at))
        CsvHistoryRepository(self._older_path).rewrite(
            self._older_path,
            sorted(older, key=lambda point: point.observed_at),
        )
