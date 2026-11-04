#!/usr/bin/env python3
"""Build the Bar-native looping animation shown while sales history loads."""

import importlib.util
import json
import math
import os
import random
import sys
import tempfile
from types import ModuleType
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 16, 16
BAR_COUNT = 8
FPS = 30
FRAME_COUNT = 120


def load_encoder(scripts: Path):
    """Loads the firmware encoder from the shared repository checkout."""
    # seq2anim imports the firmware CLI wrapper, whose optional colorlog package is only used by its CLI.
    sys.modules.setdefault("colorlog", ModuleType("colorlog"))
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("seq2anim", scripts / "seq2anim.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load animation encoder from {scripts}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BSBAnimConverter()


def color_for_row(y: int) -> tuple[int, int, int]:
    """Match the static chart palette by vertical position."""
    ratio = round((HEIGHT - 1 - y) * 29 / (HEIGHT - 1)) / 29
    return round(144 + 111 * ratio), round(232 - 187 * ratio), round(154 - 119 * ratio)


def build_frames() -> list[list[int]]:
    """Generate smoothly phased columns with no jump at the loop boundary."""
    rng = random.Random(21)
    phases = [rng.uniform(0, math.tau) for _ in range(BAR_COUNT)]
    return [
        [round(8.5 + 7.5 * math.sin(math.tau * frame / FRAME_COUNT + phase)) for phase in phases]
        for frame in range(FRAME_COUNT)
    ]


def main() -> None:
    """Render 16x16 chart frames and encode the Bar animation asset."""
    scripts = Path(os.environ.get("FIRMWARE_SCRIPTS", ROOT.parents[1] / "shared" / "busybar-firmware" / "scripts"))
    output = ROOT / "src" / "animations" / "sales_loading.anim"
    output.parent.mkdir(parents=True, exist_ok=True)
    converter = load_encoder(scripts)
    with tempfile.TemporaryDirectory() as temporary:
        frames_dir = Path(temporary)
        for index, bars in enumerate(build_frames()):
            image = Image.new("RGBA", (WIDTH, HEIGHT), (44, 44, 44, 255))
            draw = ImageDraw.Draw(image)
            for column, height in enumerate(bars):
                x0 = column * (WIDTH // BAR_COUNT)
                for y in range(HEIGHT - height, HEIGHT):
                    draw.line((x0, y, x0 + WIDTH // BAR_COUNT - 1, y), fill=(*color_for_row(y), 255))
            image.save(frames_dir / f"{index}.png")
        (frames_dir / "meta.json").write_text(json.dumps({"fps": FPS, "color_mode": "argb8888", "sections": []}))
        converter.convert_dir(frames_dir, output)
    print(f"{output}: {FRAME_COUNT} frames, {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
