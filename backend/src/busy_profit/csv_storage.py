"""CSV repositories and hourly projection publisher for sales history."""

import csv
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from busy_profit.models import SalesObservation

FIELDNAMES = ("observed_at", "bars_sold", "source_updated_at")


def csv_row(point: SalesObservation) -> dict[str, str | int]:
    """Map a typed observation into the stable flat CSV row schema."""
    return {
        "observed_at": point.observed_at.isoformat(),
        "bars_sold": point.bars_sold,
        "source_updated_at": point.source_updated_at.isoformat(),
    }


class CsvHistoryRepository:
    """Store rolling and append-only monthly history as durable CSV files."""

    def __init__(self, path: Path) -> None:
        """Set the root rolling-history path used to derive monthly archive names."""
        self._path = path

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
        """Prune rolling history, append monthly history, and return retained points."""
        cutoff = point.observed_at - timedelta(days=28)
        existing = self.read()
        retained = [item for item in existing if item.observed_at >= cutoff]
        crossed_day = (
            bool(existing)
            and existing[-1].observed_at.date() != point.observed_at.date()
        )
        if len(retained) != len(existing) or crossed_day:
            self.rewrite(self._path, retained)

        self.append(self._path, point)
        monthly_path = self._path.with_name(
            f"{self._path.stem}-{point.observed_at:%Y-%m}{self._path.suffix}",
        )
        self.append(monthly_path, point)
        return [item for item in self.read() if item.observed_at >= cutoff]


class DisplayHistoryCsvPublisher:
    """Publish daily history plus the latest 49 hourly observations atomically."""

    def __init__(self, path: Path, timezone_name: str) -> None:
        """Configure the public projection destination and display timezone."""
        self._path = path
        self._timezone = ZoneInfo(timezone_name)

    def publish(self, points: list[SalesObservation]) -> None:
        """Keep graph-resolution daily points and high-resolution recent hours."""
        by_hour: dict[datetime, SalesObservation] = {}
        by_day: dict[date, SalesObservation] = {}
        for point in points:
            local_time = point.observed_at.astimezone(self._timezone)
            hour = local_time.replace(minute=0, second=0, microsecond=0)
            by_hour[hour] = point
            by_day[local_time.date()] = point

        if not by_hour:
            CsvHistoryRepository(self._path).rewrite(self._path, [])
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
