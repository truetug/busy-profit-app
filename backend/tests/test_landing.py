"""Test README rendering and safe publication of the static landing page."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from busy_profit.landing import LandingPublisher
from website.build import build_site

ROOT = Path(__file__).resolve().parents[2]


def test_build_renders_real_readme_and_local_screenshots(tmp_path: Path) -> None:
    """Render the repository's README without duplicating its content manually.

    Keep screenshots and styling local so the page works without external CDNs.
    """
    build_site(ROOT, tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")

    assert "<h1>BUSY Profit</h1>" in html
    assert 'href="/style.css"' in html
    for screenshot in (ROOT / "screenshots").glob("*.png"):
        assert f'src="screenshots/{screenshot.name}"' in html
        assert (tmp_path / "screenshots" / screenshot.name).read_bytes() == screenshot.read_bytes()
    assert (tmp_path / "style.css").is_file()


def test_build_escapes_raw_html_in_markdown(tmp_path: Path) -> None:
    """Render Markdown as content rather than allowing injected HTML to execute.

    Preserve ordinary heading and image rendering.
    """
    source = tmp_path / "source"
    (source / "website").mkdir(parents=True)
    (source / "screenshots").mkdir()
    (source / "README.md").write_text("# Hello\n\n<script>alert(1)</script>\n", encoding="utf-8")
    (source / "website/template.html").write_text("<main><!-- README_CONTENT --></main>", encoding="utf-8")
    (source / "website/style.css").write_text("body {}", encoding="utf-8")

    output = tmp_path / "output"
    build_site(source, output)
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "<h1>Hello</h1>" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_publisher_copies_assets_before_index_and_preserves_csv(tmp_path: Path, monkeypatch) -> None:
    """Publish the index after assets without changing the sales feed.

    Replace each file atomically so clients never observe a partial file.
    """
    source = tmp_path / "built"
    (source / "screenshots").mkdir(parents=True)
    (source / "index.html").write_text("new page", encoding="utf-8")
    (source / "style.css").write_text("body {}", encoding="utf-8")
    (source / "screenshots" / "screen.png").write_bytes(b"pixels")
    (source / "screenshots" / "index.html").write_text("nested", encoding="utf-8")
    public = tmp_path / "public"
    public.mkdir()
    (public / "current.csv").write_text("untouched", encoding="utf-8")

    import busy_profit.landing as landing

    replace = landing.os.replace
    replaced: list[str] = []

    def capture_replace(src: Path, dst: Path) -> None:
        """Record the publication order while using the real atomic replacement.

        The index must only become visible after its linked assets exist.
        """
        replaced.append(Path(dst).name)
        replace(src, dst)

    monkeypatch.setattr(landing.os, "replace", capture_replace)
    LandingPublisher(source, public / "landing").publish()

    assert replaced[-1] == "index.html"
    assert (public / "landing/index.html").read_text(encoding="utf-8") == "new page"
    assert (public / "landing/screenshots/screen.png").read_bytes() == b"pixels"
    assert (public / "current.csv").read_text(encoding="utf-8") == "untouched"


def test_publisher_does_not_replace_existing_site_if_source_is_missing(tmp_path: Path) -> None:
    """Leave the last working landing page intact if no new build is present.

    A failed optional site publication must not destroy existing public files.
    """
    destination = tmp_path / "public/landing"
    destination.mkdir(parents=True)
    (destination / "index.html").write_text("old page", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        LandingPublisher(tmp_path / "missing", destination).publish()
    assert (destination / "index.html").read_text(encoding="utf-8") == "old page"


def test_landing_failure_does_not_stop_collector(monkeypatch, tmp_path: Path) -> None:
    """Keep the sales collector running if landing publication fails.

    Site generation is optional at runtime and must not interrupt polling.
    """
    import busy_profit.main as entrypoint

    settings = Mock(publish_path=tmp_path / "public/history.csv", history_path=tmp_path / "history.csv")
    settings.display_timezone = "UTC"
    collector = Mock()
    monkeypatch.setattr(entrypoint, "Settings", lambda: settings)
    monkeypatch.setattr(entrypoint, "ShopifyStatsClient", lambda _: Mock())
    monkeypatch.setattr(entrypoint, "LandingPublisher", lambda *_: Mock(publish=Mock(side_effect=OSError("failed"))))
    monkeypatch.setattr(entrypoint, "SalesCollectorService", lambda **_: collector)

    entrypoint.main()
    collector.run_forever.assert_called_once()
