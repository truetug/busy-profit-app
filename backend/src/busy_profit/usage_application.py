"""Coordinate validated usage import with an atomic persistence boundary."""

from pathlib import Path
from typing import Protocol

from busy_profit.usage_logs import read_log_batches
from busy_profit.usage_models import UsageEvent
from busy_profit.usage_parser import parse_usage_line


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


def import_usage_logs(directory: Path, store: UsageStore) -> int:
    """Map log batches to domain events and persist each completed batch once.

    Invalid and unrelated records advance the cursor without entering analytics.
    """
    count = 0
    for file_id, offset, lines in read_log_batches(directory, store):
        events = [
            event
            for line in lines
            if (event := parse_usage_line(line)) is not None
        ]
        store.commit_batch(file_id, offset, events)
        count += len(events)
    return count
