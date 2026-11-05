"""Prepare private Slack chart reports using server-side calendar projections."""

import calendar
import json
import logging
import hashlib
import time
from collections import OrderedDict
from threading import Lock
from urllib.error import HTTPError
from datetime import UTC, date, datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from collections.abc import Callable

from busy_profit.calendar_views import daily_values
from busy_profit.report_chart import render_chart
from busy_profit.slack_client import SlackClient, SlackAPIError
from busy_profit.view_service import ViewService
from busy_profit.view_storage import ObservationIndex


class SlackReports:
    """Deliver personal reports without exposing sales through public image URLs."""

    def __init__(self, client: SlackClient, token: Callable[[], str], views: ViewService, index: ObservationIndex) -> None:
        """Inject Slack infrastructure and aggregation use cases.

        Channel reports remain separate until destination checks are implemented.
        """
        self._client, self._token, self._views, self._index = client, token, views, index
        self._files: OrderedDict[str, str] = OrderedDict()
        self._chart_lock = Lock()

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
            channel_id = fields.get("channel_id", "")
            publish = channel_id.startswith(("C", "G"))
            if publish:
                stage = "channel"
                channel = self._client.call("conversations.info", {"channel": channel_id}, token)["channel"]
                if channel.get("is_ext_shared") or channel.get("is_shared") or not channel.get("is_member"):
                    raise ValueError("Only internal joined channels are supported")
                timezone = "UTC"
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
            key = hashlib.sha256(json.dumps([title, timezone, labels, values, channel_id if publish else "private"]).encode()).hexdigest()
            newly_shared = False
            with self._chart_lock:
                file_id = self._files.get(key)
                if file_id is None:
                    png = render_chart(title, timezone, labels, values)
                    stage = "upload"
                    if publish:
                        file_id = self._client.upload_chart(png, f"{title} · {timezone}", token, channel_id)
                        newly_shared = True
                    else:
                        file_id = self._client.upload_chart(png, title, token)
                    self._files[key] = file_id
                    if len(self._files) > 64:
                        self._files.popitem(last=False)
                else:
                    self._files.move_to_end(key)
            stage = "delivery"
            if newly_shared:
                return
            delivery = {
                "channel": fields["channel_id"],
                "user": fields["user_id"],
                "text": f"{title} · {timezone}",
                "blocks": json.dumps([{"type": "image", "slack_file": {"id": file_id}, "alt_text": f"{title} · {timezone}"}]),
            }
            for attempt in range(4):
                try:
                    if publish:
                        delivery.pop("user", None)
                    self._client.call("chat.postMessage" if publish else "chat.postEphemeral", delivery, token)
                    break
                except SlackAPIError as error:
                    if error.code != "invalid_blocks" or attempt == 3:
                        raise
                    time.sleep((3, 5, 8)[attempt])
        except Exception as error:
            logging.getLogger("busy_profit.slack").warning("Report failed stage=%s error=%s", stage, type(error).__name__)
            self._respond(response_url, {"response_type": "ephemeral", "text":
                f"Report unavailable at {stage}. Please retry. If it repeats, report this stage."})

    def _respond(self, url: str, payload: dict) -> None:
        """Post a private response without logging the secret response URL.

        The caller has validated its Slack hostname before any work starts.
        """
        try:
            with urlopen(Request(url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}), timeout=8) as response:
                response.read(1024)
        except HTTPError as error:
            raw = error.read(4096).decode("utf-8", errors="replace")
            known = ["invalid_blocks", "invalid_payload", "file_not_found", "image_not_found", "channel_not_found", "invalid_response_url", "expired"]
            reason = next((code for code in known if code in raw), "unclassified")
            logging.getLogger("busy_profit.slack").warning("Slack delivery HTTP=%s reason=%s", error.code, reason)
            raise
