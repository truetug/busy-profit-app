"""Render the established Profit pixel-chart design at Slack icon resolution."""

import struct
import zlib
from pathlib import Path

from make_app_icons import chunk


def main() -> None:
    """Draw a 512-pixel square using the app icon's six-column palette.

    Use integer logical pixels and let Slack supply the background color.
    """
    size = 512
    colors = [(99, 181, 74), (138, 187, 61), (177, 185, 54),
              (206, 177, 50), (233, 134, 46), (222, 82, 54)]
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            column = x // 64 - 1
            lit = 0 <= column < 6 and 6 - (column + 1) < y // 64 <= 6
            rows.extend((*colors[column], 255) if lit else (0, 0, 0, 0))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    output = Path(__file__).resolve().parents[1] / "slack" / "icon.png"
    output.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    main()
