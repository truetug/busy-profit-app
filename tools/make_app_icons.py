"""Generate the app's small pixel-art sales chart icons without dependencies."""

import struct
import zlib
from pathlib import Path


def chunk(kind: bytes, data: bytes) -> bytes:
    """Encode a PNG chunk with its length and checksum.

    Keep the generated icon assets reproducible across development machines.
    """
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def icon(size: int, heights: list[int], colors: list[tuple[int, int, int]]) -> bytes:
    """Draw contiguous sales columns with transparent padding around the chart.

    Encode RGBA pixels as a standards-compliant PNG without external libraries.
    """
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            index = x - 1
            bar = 0 <= index < len(heights) and size - 2 - heights[index] < y <= size - 2
            if bar:
                rows.extend((*colors[index], 255))
            else:
                rows.extend((0, 0, 0, 0))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def main() -> None:
    """Generate the front colour and rear grayscale icons in app metadata.

    The charts use the same low-green, high-red language as the app display.
    """
    target = Path(__file__).resolve().parents[1] / "src" / "appmeta"
    target.joinpath("icon_front_8x8.png").write_bytes(icon(
        8,
        [1, 2, 3, 4, 5, 6],
        [(99, 181, 74), (138, 187, 61), (177, 185, 54), (206, 177, 50), (233, 134, 46), (222, 82, 54)],
    ))
    target.joinpath("icon_back_11x11.png").write_bytes(icon(
        11,
        [1, 2, 3, 4, 5, 6, 7, 8, 9],
        [(150, 150, 150)] * 9,
    ))


if __name__ == "__main__":
    main()
