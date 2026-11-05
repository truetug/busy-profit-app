"""Incrementally index private CSV archives for API projection."""

from pathlib import Path

from busy_profit.csv_storage import CsvHistoryRepository
from busy_profit.view_storage import ObservationIndex


class ArchiveImporter:
    """Track source signatures without reading unchanged closed months."""

    def __init__(self, history: Path, index: ObservationIndex) -> None:
        """Bind the source repository and destination index.

        Signature state is deliberately disposable and rebuilt after restart.
        """
        self._history = history
        self._index = index
        self._repository = CsvHistoryRepository(history)
        self._signatures: dict[Path, tuple[int, int]] = {}

    def refresh(self) -> None:
        """Import changed files, including corrected historical totals.

        Only mark a file imported after validation and successful commit.
        """
        paths = sorted(self._history.parent.glob(f"{self._history.stem}-*{self._history.suffix}"))
        for path in paths:
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if self._signatures.get(path) == signature:
                continue
            self._index.import_points(self._repository.read(path))
            self._signatures[path] = signature
