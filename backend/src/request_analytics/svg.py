"""Render aggregate-only usage statistics as responsive static SVG assets."""

import os
from html import escape
from pathlib import Path
from textwrap import wrap

from request_analytics.models import UsageSummary
from request_analytics.profile import InfographicLabels


def render_usage_svg(
    summary: UsageSummary,
    mobile: bool = False,
    labels: InfographicLabels | None = None,
) -> str:
    """Draw metric cards and zero-based daily bars without external assets.

    Preserve missing history and label incomplete and observational measurements.
    """
    labels = labels or InfographicLabels()
    width, height = (480, 1020) if mobile else (1000, 680)
    columns = 2 if mobile else 4
    card_width = (width - 64 - (columns - 1) * 12) / columns
    cards = [(f"ACTIVE {labels.devices.upper()}", summary.active), (f"NEW {labels.devices.upper()}", summary.new), ("RETURNING", summary.returning), ("REGULAR · 3+ DAYS", summary.regular), ("APP STARTS", summary.starts), ("DETAIL OPENS", summary.details), ("OBSERVED HOURS", round(summary.runtime_seconds / 3600, 1) if summary.runtime_seconds is not None else None)]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">', f'<title id="title">{escape(labels.title)}</title>', '<desc id="desc">Aggregate device activity. Missing history is not zero. Session metrics are observed since instrumentation began.</desc>', f'<rect width="{width}" height="{height}" rx="20" fill="#191d17"/>', '<style>text{font-family:Arial,sans-serif;fill:#e8e9e2}.muted{fill:#a8af9e}.label{font-size:13px;letter-spacing:1px}.value{font-size:34px;font-weight:700}.small{font-size:13px}</style>']
    updated = summary.generated_at.strftime("%d %b %Y · %H:%M UTC")
    parts.append('<text x="32" y="42" font-size="22" font-weight="700">COMMUNITY USAGE</text>')
    parts.append(f'<text x="{32 if mobile else width-32}" y="{68 if mobile else 42}" text-anchor="{"start" if mobile else "end"}" class="muted small">Updated {escape(updated)}</text>')
    parts.append(f'<text x="32" y="{94 if mobile else 70}" class="muted small">Last 7 calendar days · UTC · today partial</text>')
    top = 116 if mobile else 94
    for index, (label, value) in enumerate(cards):
        x = 32 + (index % columns) * (card_width + 12)
        y = top + (index // columns) * 100
        parts.append(f'<rect x="{x}" y="{y}" width="{card_width}" height="88" rx="8" fill="#242a20"/><text x="{x+16}" y="{y+25}" class="muted label">{escape(label)}</text><text x="{x+16}" y="{y+65}" class="value">{value if value is not None else "—"}</text>')
    chart_top = 560 if mobile else 330
    baseline = chart_top + 180
    parts.append(f'<text x="32" y="{chart_top-20}" font-size="18" font-weight="700">Active {escape(labels.devices)} by day</text>')
    parts.append(f'<path d="M32 {baseline}H{width-32}" stroke="#66705d"/>')
    maximum = max(1, max((day.active or 0 for day in summary.days), default=0))
    step = (width - 64) / 7
    for index, day in enumerate(summary.days):
        center = 32 + step * (index + 0.5)
        bar_height = 145 * (day.active or 0) / maximum
        if day.active is not None:
            parts.append(f'<rect x="{center-step*.3}" y="{baseline-bar_height}" width="{step*.6}" height="{bar_height}" rx="3" fill="#e9b35c"/>')
        value = str(day.active) if day.active is not None else "—"
        parts.append(f'<text x="{center}" y="{baseline-bar_height-10}" text-anchor="middle" font-size="18">{value}</text><text x="{center}" y="{baseline+26}" text-anchor="middle" class="muted small">{day.day.strftime("%d %b")}</text>')
    since = summary.session_since.strftime("%d %b %Y") if summary.session_since else "not yet available"
    notes = ["New = first seen this week. Returning = first seen earlier.", f"Regular = active on 3+ days. Counts refer to {labels.devices}, not people.", f"Session metrics since {since}; final interval may be missing.", "— means not yet observed. No IPs or device IDs are published."]
    note_y = baseline + 62
    for note in notes:
        if mobile:
            note = note.replace("Session metrics: reported by the app; final partial minute may be missing.", "Runtime excludes the unreported final interval.").replace("New = first seen this week. Returning = first seen earlier.", "New: first seen this week. Returning: seen earlier.")
        for line in wrap(note, 55) if mobile else [note]:
            parts.append(f'<text x="32" y="{note_y}" class="muted small">{escape(line)}</text>')
            note_y += 21
    parts.append('</svg>')
    return "".join(parts)


def publish_usage_infographic(
    summary: UsageSummary,
    directory: Path,
    labels: InfographicLabels | None = None,
) -> None:
    """Atomically replace public desktop and mobile assets after a successful import.

    Only the aggregate summary is serializable into these publicly served images.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for name, mobile in (("usage.svg", False), ("usage-mobile.svg", True)):
        target = directory / name
        temporary = directory / f".{name}.tmp"
        temporary.write_text(render_usage_svg(summary, mobile, labels), encoding="utf-8")
        temporary.chmod(0o644)
        os.replace(temporary, target)
