"""Publish generated landing assets into the read-only web server's directory."""

import os
import shutil
from pathlib import Path


class LandingPublisher:
    """Copy the built landing page without touching private sales history."""

    def __init__(self, source: Path, destination: Path) -> None:
        """Configure the image asset directory and the public landing directory.

        The destination is separate from the collector's CSV files.
        """
        self._source = source
        self._destination = destination

    def publish(self) -> None:
        """Replace generated files atomically, publishing the index last.

        Previously published assets remain available while the new page is copied.
        """
        if not (self._source / "index.html").is_file():
            raise FileNotFoundError("built landing index is missing")
        files = sorted(
            (path for path in self._source.rglob("*") if path.is_file()),
            key=lambda path: (path.relative_to(self._source) == Path("index.html"), str(path)),
        )
        for source in files:
            if source.is_symlink():
                raise ValueError("landing assets must not contain symlinks")
            destination = self._destination / source.relative_to(self._source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.tmp")
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
