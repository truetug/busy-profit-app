"""Coordinate polling, domain validation, persistence, and publication."""

import json
import logging
import time
from datetime import UTC, datetime
from typing import Protocol

from busy_profit.models import SalesObservation
from busy_profit.settings import Settings

LOG = logging.getLogger("busy_profit")


class SalesSource(Protocol):
    """Describe the source port used to fetch the current cumulative count."""

    def fetch_count(self) -> tuple[int, datetime]:
        """Return the current BUSY Bar count and source update timestamp."""
        ...


class HistoryRepository(Protocol):
    """Describe the persistence port for collected sales observations."""

    def save(self, point: SalesObservation) -> list[SalesObservation]:
        """Persist an observation and return the retained rolling history."""
        ...


class HistoryPublisher(Protocol):
    """Describe the output port for the compact public display projection."""

    def publish(self, points: list[SalesObservation]) -> None:
        """Publish retained points in the compact format consumed by the app."""
        ...


class SalesCollectorService:
    """Run the collection use case using injected source and storage ports."""

    def __init__(
        self,
        settings: Settings,
        source: SalesSource,
        repository: HistoryRepository,
        publisher: HistoryPublisher,
    ) -> None:
        """Keep runtime policy and port implementations for repeated polling."""
        self._settings = settings
        self._source = source
        self._repository = repository
        self._publisher = publisher

    def poll_once(self) -> SalesObservation:
        """Fetch, validate, persist, and publish one current sales snapshot."""
        bars_sold, source_updated_at = self._source.fetch_count()
        point = SalesObservation(
            observed_at=datetime.now(UTC),
            bars_sold=bars_sold,
            source_updated_at=source_updated_at,
        )
        history = self._repository.save(point)
        self._publisher.publish(history)
        LOG.info(
            json.dumps(
                {
                    "event": "sales_poll_completed",
                    "bars_sold": point.bars_sold,
                    "history_points": len(history),
                },
            ),
        )
        return point

    def run_forever(self) -> None:
        """Poll at the configured cadence and log transient failures for retry."""
        while True:
            started_at = time.monotonic()
            try:
                self.poll_once()
            except Exception as error:
                LOG.error(
                    json.dumps(
                        {
                            "event": "sales_poll_failed",
                            "error": f"{type(error).__name__}: {error}",
                        },
                    ),
                )
            time.sleep(
                max(
                    0,
                    self._settings.polling_interval_seconds
                    - (time.monotonic() - started_at),
                ),
            )
