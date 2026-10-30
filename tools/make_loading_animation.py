#!/usr/bin/env python3
"""Build the Bar-native looping animation shown while sales history loads."""

import importlib.util
import json
import os
import random
import sys
import tempfile
from types import ModuleType
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 16, 16
FPS = 3
FRAME_COUNT = 32


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


def color_for_height(height: int) -> tuple[int, int, int]:
    """Maps short columns to green and tall columns to red, matching the Pi chart palette."""
    ratio = (height - 1) / (HEIGHT - 1)
    return round(35 + 220 * ratio), round(175 - 130 * ratio), round(75 - 40 * ratio)


def build_frames() -> list[list[int]]:
    """Creates a cyclic random-walk sequence so adjacent animation frames feel organic."""
    rng = random.Random(21)
    bars = [rng.randint(2, HEIGHT - 2) for _ in range(4)]
    frames = [bars.copy()]
    for _ in range(FRAME_COUNT - 2):
        bars = [max(1, min(HEIGHT, value + rng.randint(-4, 4))) for value in bars]
        frames.append(bars.copy())
    frames.append(frames[0].copy())
    return frames


def main() -> None:
    """Renders transparent 16x16 sales-chart frames and encodes the Bar animation asset."""
    scripts = Path(os.environ.get("FIRMWARE_SCRIPTS", ROOT.parents[1] / "shared" / "busybar-firmware" / "scripts"))
    output = ROOT / "src" / "animations" / "sales_loading.anim"
    output.parent.mkdir(parents=True, exist_ok=True)
    converter = load_encoder(scripts)
    with tempfile.TemporaryDirectory() as temporary:
        frames_dir = Path(temporary)
        for index, bars in enumerate(build_frames()):
            image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            for column, height in enumerate(bars):
                x0 = column * (WIDTH // 4)
                draw.rectangle((x0, HEIGHT - height, x0 + WIDTH // 4 - 1, HEIGHT - 1), fill=(*color_for_height(height), 255))
            image.save(frames_dir / f"{index}.png")
        (frames_dir / "meta.json").write_text(json.dumps({"fps": FPS, "color_mode": "argb8888", "sections": []}))
        converter.convert_dir(frames_dir, output)
    print(f"{output}: {FRAME_COUNT} frames, {output.stat().st_size} bytes")


if __name__ == "__main__":
    main()
