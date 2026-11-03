"""Build a static landing page from the repository README and screenshots."""

import shutil
from pathlib import Path

from markdown_it import MarkdownIt
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def build_share_card(source: Path, output: Path) -> None:
    """Compose a social preview from the real icon and demo device screenshot.

    Use a standard 1200 by 630 canvas and nearest-neighbor screen enlargement.
    """
    card = Image.new("RGB", (1200, 630), "#111310")
    draw = ImageDraw.Draw(card)
    icon = Image.open(source / "src/appmeta/icon_front_8x8.png").convert("RGBA")
    icon = icon.resize((64, 64), Image.Resampling.NEAREST)
    card.paste(icon, (72, 64), icon)
    draw.text((160, 59), "BUSY Profit", font=ImageFont.load_default(size=64), fill="#f7f7ee")
    draw.text((72, 164), "Live sales, daily trends and new-sale alerts.", font=ImageFont.load_default(size=30), fill="#bfc3b7")
    draw.rounded_rectangle((72, 260, 1128, 532), radius=20, fill="#000000", outline="#353e2d", width=2)
    screen = Image.open(source / "screenshots/catalog/lifetime-summary.png").convert("RGB")
    card.paste(screen.resize((1008, 224), Image.Resampling.NEAREST), (96, 284))
    draw.text((72, 570), "profit.busy.truetug.info", font=ImageFont.load_default(size=22), fill="#e9b35c")
    draw.text((1128, 570), "Demo screen", anchor="rt", font=ImageFont.load_default(size=22), fill="#929a87")
    card.save(output / "screenshots/share-card.png", optimize=True)


def build_site(source: Path, output: Path) -> None:
    """Render the README and copy the local page assets into the output folder.

    Disable raw HTML in Markdown so the content cannot inject executable markup.
    """
    readme = (source / "README.md").read_text(encoding="utf-8")
    template = (source / "website/template.html").read_text(encoding="utf-8")
    marker = "<!-- README_CONTENT -->"
    if template.count(marker) != 1:
        raise ValueError("landing template must contain one README content marker")
    body = MarkdownIt("commonmark", {"html": False}).render(readme)
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(template.replace(marker, body), encoding="utf-8")
    shutil.copy2(source / "website/style.css", output / "style.css")
    shutil.copytree(source / "screenshots", output / "screenshots", dirs_exist_ok=True)
    shutil.copy2(source / "src/appmeta/icon_front_8x8.png", output / "screenshots/app-icon.png")
    build_share_card(source, output)


if __name__ == "__main__":
    build_site(ROOT, ROOT / "website/dist")
