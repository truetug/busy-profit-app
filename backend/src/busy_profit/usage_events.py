"""Record private application events for aggregate community statistics."""

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
import os


class UsageEvents:
    """Separate application activity from transport request counts."""

    def __init__(self, path: Path) -> None:
        """Create a private event journal and stable subject first-seen registry.

        Subjects are internal Slack identities or device IDs, never public output.
        """
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS subjects (kind TEXT, subject TEXT, first_seen INTEGER, PRIMARY KEY(kind,subject))")
            connection.execute("CREATE TABLE IF NOT EXISTS events (at INTEGER NOT NULL, kind TEXT NOT NULL, subject TEXT NOT NULL, action TEXT NOT NULL)")
            connection.execute("CREATE INDEX IF NOT EXISTS events_time ON events(at)")
        path.chmod(0o600)

    def record(self, kind: str, subject: str, action: str, now: datetime | None = None) -> None:
        """Persist a bounded classified event without credentials or message text.

        Issuance events are distinct from successful data reads and deliveries.
        """
        allowed = {"employee": {"pin_issued", "data_read", "slack_day", "slack_month"},
                   "shared": {"data_read"}, "bar": {"data_read"}}
        if kind not in allowed or action not in allowed[kind] or not subject or len(subject) > 128:
            raise ValueError("Invalid usage event")
        at = int((now or datetime.now(UTC)).timestamp())
        with sqlite3.connect(self._path) as connection:
            connection.execute("INSERT OR IGNORE INTO subjects VALUES (?,?,?)", (kind, subject, at))
            connection.execute("INSERT INTO events VALUES (?,?,?,?)", (at, kind, subject, action))
            connection.execute("DELETE FROM events WHERE at<?", (at - 90*86400,))

    def summary(self, now: datetime) -> dict[str, int]:
        """Return aggregates for seven UTC calendar days including partial today.

        Credential issuance never counts as active application use.
        """
        cutoff = int((now.astimezone(UTC).replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=6)).timestamp())
        end = int(now.timestamp())
        with sqlite3.connect(self._path) as connection:
            active = connection.execute("SELECT count(DISTINCT subject) FROM events WHERE kind='employee' AND action!='pin_issued' AND at BETWEEN ? AND ?", (cutoff,end)).fetchone()[0]
            new = connection.execute("SELECT count(DISTINCT e.subject) FROM events e JOIN subjects s ON s.kind=e.kind AND s.subject=e.subject WHERE e.kind='employee' AND e.action!='pin_issued' AND e.at BETWEEN ? AND ? AND s.first_seen>=?", (cutoff,end,cutoff)).fetchone()[0]
            reports = connection.execute("SELECT action,count(*) FROM events WHERE action IN ('slack_day','slack_month') AND at BETWEEN ? AND ? GROUP BY action", (cutoff,end)).fetchall()
            bars = connection.execute("SELECT count(DISTINCT subject) FROM events WHERE kind='bar' AND at BETWEEN ? AND ?", (cutoff,end)).fetchone()[0]
            issued = connection.execute("SELECT count(*) FROM subjects WHERE kind='employee'").fetchone()[0]
        return {"active_employees": active, "new_employees": new, "returning_employees": active-new,
                "active_bars": bars, "employees_seen": issued,
                "day_reports": dict(reports).get("slack_day",0), "month_reports": dict(reports).get("slack_month",0)}


def append_activity_panel(directory: Path, now: datetime) -> None:
    """Add aggregate account and Slack cards to existing device infographics.

    Keep old device metrics separate and state when new instrumentation began.
    """
    database = directory.parent / "activity.sqlite3"
    if not database.exists():
        return
    summary = UsageEvents(database).summary(now)
    holders = 0
    access = directory.parent / "access.sqlite3"
    if access.exists():
        with sqlite3.connect(f"file:{access}?mode=ro", uri=True) as connection:
            holders = connection.execute("SELECT count(*) FROM access_codes WHERE workspace!='system'").fetchone()[0]
    cards = [("ACTIVE EMPLOYEES",summary["active_employees"]),
             ("NEW ACTIVE",summary["new_employees"]),
             ("RETURNING",summary["returning_employees"]),
             ("PERSONAL ACCESS HOLDERS",holders),
             ("DAY REPORTS DELIVERED",summary["day_reports"]),
             ("MONTH REPORTS DELIVERED",summary["month_reports"])]
    for filename, width, base, extra in [("usage.svg",1000,680,300),("usage-mobile.svg",480,1020,580)]:
        path = directory / filename
        if not path.exists():
            continue
        svg = path.read_text()
        columns = 3 if width == 1000 else 2
        parts = [f'<rect x="0" y="{base}" width="{width}" height="{extra}" rx="20" fill="#191d17"/>',
            f'<text x="32" y="{base+35}" font-size="20">EMPLOYEES &amp; SLACK · LAST 7 DAYS</text>',
            f'<text x="32" y="{base+60}" font-size="12" fill="#a8af9e">Account events collected since 5 Nov 2026 · UTC · today partial</text>']
        cell = (width-64)//columns
        for index,(label,value) in enumerate(cards):
            x = 32+(index%columns)*cell
            y = base+100+(index//columns)*85
            parts.extend([f'<text x="{x}" y="{y}" font-size="11">{label}</text>',
                          f'<text x="{x}" y="{y+38}" font-size="30" font-weight="700">{value}</text>'])
        svg = svg.replace(f'viewBox="0 0 {width} {base}"',f'viewBox="0 0 {width} {base+extra}"')
        svg = svg.replace("</svg>","".join(parts)+"</svg>")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(svg)
        os.replace(temporary,path)
