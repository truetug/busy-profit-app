"""Check private chart output and explicit presentation context."""

from io import BytesIO
from datetime import date

from PIL import Image
import pytest

from busy_profit.report_chart import render_chart
from busy_profit.report_menu import report_menu


def test_png_chart_handles_unknown_and_zero_sales() -> None:
    """Render valid PNGs without treating unknown buckets as zero.

    The chart uses fixed dimensions and has no public asset dependency.
    """
    image = Image.open(BytesIO(render_chart("Day · 2026-11-05", "UTC", ["00", "01", "02"], [None, 0, 10])))
    assert image.size == (1200, 640)
    assert image.getpixel((82, 520)) == (96, 96, 96)
    with pytest.raises(ValueError):
        render_chart("Invalid", "UTC", ["00"], [-1])


def test_menu_is_private_and_has_timezone_context() -> None:
    """Keep report requests private until explicit publication.

    The menu states the separate personal and channel timezone policies.
    """
    menu = report_menu(date(2026, 11, 5), "Europe/Moscow")
    assert menu["response_type"] == "ephemeral"
    assert "UTC" in menu["blocks"][1]["elements"][0]["text"]
