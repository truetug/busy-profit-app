"""Build a static landing page from the repository README and screenshots."""

import shutil
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    build_site(ROOT, ROOT / "website/dist")
