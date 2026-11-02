"""Build a dim native animated chart behind new-sales digits."""

import json
import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from make_loading_animation import load_encoder

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Encode a seamless five-second chart cycle without runtime JavaScript timers."""
    converter = load_encoder(ROOT.parents[1] / "shared/busybar-firmware/scripts")
    output = ROOT / "src/animations/sales_notification.anim"
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        for frame in range(20):
            image = Image.new("RGBA", (72, 16), (0, 0, 0, 255))
            draw = ImageDraw.Draw(image)
            for bar in range(36):
                height = round(8 + 7 * math.sin(frame * math.tau / 20 + bar * 0.7))
                ratio = height / 15
                color = (round(12 + 42 * ratio), round(40 - 28 * ratio), 10, 255)
                draw.rectangle((bar * 2, 16 - height, bar * 2 + 1, 15), fill=color)
            image.save(folder / f"{frame}.png")
        (folder / "meta.json").write_text(json.dumps({"fps": 4, "color_mode": "argb8888", "sections": []}))
        converter.convert_dir(folder, output)


if __name__ == "__main__":
    main()
