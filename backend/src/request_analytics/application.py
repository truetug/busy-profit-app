"""Coordinate validated usage import with an atomic persistence boundary."""

from datetime import datetime
from pathlib import Path
from typing import Protocol

from request_analytics.logs import read_log_batches
from request_analytics.models import AnalyticsResult, UsageEvent, UsageSummary
from request_analytics.caddy import parse_usage_line
from request_analytics.profile import AnalyticsProfile


class UsageStore(Protocol):
    """Define the persistence port used by the incremental import use case."""

    def offset(self, file_id: str) -> int:
        """Return the last committed byte offset for one stable file identity.

        An unknown identity begins at the start of its log file.
        """
        ...

    def commit_batch(self, file_id: str, offset: int, events: list[UsageEvent]) -> None:
        """Commit usage events and their ending byte offset atomically.

        Failed writes must leave both events and checkpoint unchanged.
        """
        ...


def import_usage_logs(directory: Path, store: UsageStore, profile: AnalyticsProfile) -> int:
    """Map log batches to domain events and persist each completed batch once.

    Invalid and unrelated records advance the cursor without entering analytics.
    """
    count = 0
    for file_id, offset, lines in read_log_batches(directory, store, profile.log_pattern):
        events = [
            event
            for line in lines
            if (event := parse_usage_line(line, profile)) is not None
        ]
        store.commit_batch(file_id, offset, events)
        count += len(events)
    return count


class AnalyticsStore(UsageStore, Protocol):
    """Define aggregate maintenance independently of a storage implementation."""

    def prune(self, now: datetime, retention_days: int) -> None:
        """Expire detailed records according to the host's retention policy.

        Preserve the aggregate identity history required for new/returning metrics.
        """
        ...

    def weekly_summary(self, now: datetime) -> UsageSummary:
        """Return an identifier-free summary of the seven-day observation window.

        Missing coverage must remain distinguishable from measured zero activity.
        """
        ...


class SummaryPublisher(Protocol):
    """Accept a public aggregate projection without access to private storage."""

    def __call__(self, summary: UsageSummary) -> None:
        """Publish a complete aggregate summary through the selected output adapter.

        Never receive raw requests, hardware identities or source IP addresses.
        """
        ...


def refresh_usage(
    directory: Path,
    store: AnalyticsStore,
    profile: AnalyticsProfile,
    publisher: SummaryPublisher,
    now: datetime,
    retention_days: int = 90,
) -> AnalyticsResult:
    """Import requests, maintain retention, and publish an aggregate projection.

    Keep scheduling, process lifecycle, logging and credentials in the host worker.
    """
    count = import_usage_logs(directory, store, profile)
    store.prune(now, retention_days)
    summary = store.weekly_summary(now)
    publisher(summary)
    return AnalyticsResult(imported_records=count, summary=summary)
