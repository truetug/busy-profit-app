"""Publish a compact hourly CSV for the Busy Bar JS application."""

import csv
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from busy_shopify_stats.model import SalesHistoryPoint


class CsvHourlyHistoryPublisher:
    """Atomically publish the latest cumulative sample from each local hour."""

    _fieldnames = ("observed_at", "bars_sold", "source_updated_at")

    def __init__(self, path: Path, timezone: str) -> None:
        """Configure output and local time grouping.

        The output is replaced atomically so Caddy never serves a partial CSV.
        """
        self._path = path
        self._timezone = ZoneInfo(timezone)

    def publish(self, points: list[SalesHistoryPoint]) -> None:
        """Replace the public CSV with one cumulative row per local hour.

        Raw minute samples and month archives remain in the private data folder;
        the public projection is bounded to roughly 672 rows.
        """
        hourly: dict[datetime, SalesHistoryPoint] = {}
        for point in points:
            local = point.observed_at.astimezone(self._timezone)
            hour = local.replace(minute=0, second=0, microsecond=0)
            hourly[hour] = point

        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._path.with_name(f".{self._path.name}.tmp")
        with temporary_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=self._fieldnames)
            writer.writeheader()
            for point in sorted(hourly.values(), key=lambda item: item.observed_at):
                writer.writerow(
                    {
                        "observed_at": point.observed_at.isoformat(),
                        "bars_sold": point.bars_sold,
                        "source_updated_at": point.source_updated_at.isoformat(),
                    },
                )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, self._path)
