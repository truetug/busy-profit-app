"""Prepare private Slack chart reports using server-side calendar projections."""

import calendar
import json
import logging
from datetime import UTC, date, datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from collections.abc import Callable

from busy_profit.calendar_views import daily_values
from busy_profit.report_chart import render_chart
from busy_profit.slack_client import SlackClient
from busy_profit.view_service import ViewService
from busy_profit.view_storage import ObservationIndex


class SlackReports:
    """Deliver personal reports without exposing sales through public image URLs."""

    def __init__(self, client: SlackClient, token: Callable[[], str], views: ViewService, index: ObservationIndex) -> None:
        """Inject Slack infrastructure and aggregation use cases.

        Channel reports remain separate until destination checks are implemented.
        """
        self._client, self._token, self._views, self._index = client, token, views, index

    def execute(self, fields: dict[str, str]) -> None:
        """Build one requested report and post it through the signed response URL.

        Return a private help message for an empty or unsupported command.
        """
        response_url = fields.get("response_url", "")
        parsed = urlparse(response_url)
        if parsed.scheme != "https" or parsed.hostname != "hooks.slack.com" or not parsed.path.startswith("/commands/"):
            return
        stage = "token"
        try:
            token = self._token()
            stage = "profile"
            member = self._client.member(fields["user_id"], token)
            if not member.tz:
                raise ValueError("Set your Slack profile timezone first")
            timezone = member.tz
            today = datetime.now(ZoneInfo(timezone)).date()
            args = fields.get("text", "").strip().split()
            mode = args[0] if args else ""
            stage = "projection"
            if mode == "day":
                day = date.fromisoformat(args[1]) if len(args) > 1 else today
                if day < date(2026, 7, 14) or day > today:
                    raise ValueError("Date outside the sales period")
                report = self._views.hours(timezone, day)
                title = f"Hourly sales · {day}"
                labels = [at.strftime("%H:%M %z") for at in report.starts]
                values = report.values
            elif mode == "month":
                month = date.fromisoformat(args[1] + "-01") if len(args) > 1 else today.replace(day=1)
                if month > today or month < date(2026, 7, 1):
                    raise ValueError("Month outside the sales period")
                days = calendar.monthrange(month.year, month.month)[1]
                if month.year == today.year and month.month == today.month:
                    days = today.day
                with self._index.snapshot() as source:
                    values = daily_values(source, month, days, timezone)
                title = f"Daily sales · {month:%Y-%m}"
                labels = [str(index+1) for index in range(days)]
            else:
                self._respond(response_url, {"response_type": "ephemeral", "text":
                    "BUSY Profit\n/profit day [YYYY-MM-DD] — hourly chart\n/profit month [YYYY-MM] — daily chart\n/profit access — personal Bar PIN\nPersonal reports use your Slack profile timezone."})
                return
            stage = "render"
            png = render_chart(title, timezone, labels, values)
            stage = "upload"
            file_id = self._client.upload_chart(png, title, token)
            stage = "delivery"
            self._respond(response_url, {"response_type": "ephemeral", "text": f"{title} · {timezone}",
                "blocks": [{"type": "image", "slack_file": {"id": file_id}, "alt_text": f"{title} · {timezone}"}]})
        except Exception as error:
            logging.getLogger("busy_profit.slack").warning("Report failed stage=%s error=%s", stage, type(error).__name__)
            self._respond(response_url, {"response_type": "ephemeral", "text":
                f"Report unavailable at {stage}. Please retry. If it repeats, report this stage."})

    def _respond(self, url: str, payload: dict) -> None:
        """Post a private response without logging the secret response URL.

        The caller has validated its Slack hostname before any work starts.
        """
        with urlopen(Request(url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}), timeout=8) as response:
            response.read(1024)
