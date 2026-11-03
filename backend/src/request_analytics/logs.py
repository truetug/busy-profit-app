"""Read bounded complete-line batches from uncompressed rotating Caddy logs."""

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol


class LogCheckpoints(Protocol):
    """Expose persisted file offsets without coupling the reader to SQLite."""

    def offset(self, file_id: str) -> int:
        """Return the committed offset for an inode-based file identity.

        Renames retain this identity through uncompressed log rotation.
        """
        ...


def read_log_batches(
    directory: Path,
    checkpoints: LogCheckpoints,
    pattern: str = "*.json",
) -> Iterator[tuple[str, int, list[bytes]]]:
    """Yield bounded batches and stop before incomplete records at the file tail.

    Caddy must use uncompressed rename rotation so inode checkpoints stay valid.
    """
    paths = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime_ns)
    for path in paths:
        try:
            with path.open("rb") as source:
                stat = os.fstat(source.fileno())
                prefix = source.readline(1024 * 1024)
                if not prefix.endswith(b"\n"):
                    continue
                fingerprint = hashlib.sha256(prefix).hexdigest()[:24]
                file_id = f"{stat.st_dev}:{stat.st_ino}:{fingerprint}"
                source.seek(0)
                offset = checkpoints.offset(file_id)
                source.seek(offset if offset <= stat.st_size else 0)
                while True:
                    start = source.tell()
                    position = start
                    lines: list[bytes] = []
                    for _ in range(1000):
                        line = source.readline(1024 * 1024)
                        if not line.endswith(b"\n"):
                            source.seek(position)
                            break
                        position = source.tell()
                        lines.append(line)
                        if position - start >= 2 * 1024 * 1024:
                            break
                    if position != start:
                        yield file_id, position, lines
                    if not line.endswith(b"\n"):
                        break
        except FileNotFoundError:
            continue
