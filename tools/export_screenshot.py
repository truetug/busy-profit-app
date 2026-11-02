"""Export a real Bar framebuffer in native catalog and enlarged documentation sizes."""

import argparse
import base64
from pathlib import Path

from PIL import Image


def main() -> None:
    """Decode the API's base64 BGR24 bytes without smoothing or altering pixels."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("name", choices=("lifetime-summary", "daily-chart", "new-sales"))
    args = parser.parse_args()
    image = Image.frombytes("RGB", (72, 16), base64.b64decode(args.input.read_bytes()), "raw", "BGR")
    output = Path(__file__).resolve().parents[1] / "screenshots"
    (output / "catalog").mkdir(parents=True, exist_ok=True)
    image.save(output / "catalog" / f"{args.name}.png")
    image.resize((1152, 256), Image.Resampling.NEAREST).save(output / f"{args.name}.png")


if __name__ == "__main__":
    main()
