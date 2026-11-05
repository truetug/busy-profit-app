"""Verify image blocks are delivered with the uploading bot's identity."""

from types import SimpleNamespace
from datetime import UTC, datetime

from busy_profit.slack_reports import SlackReports


def test_chart_uses_authenticated_private_delivery_and_reuses_file() -> None:
    """Do not send Slack file image blocks through anonymous response URLs.

    Repeated identical requests reuse the uploaded file instead of rerendering.
    """
    calls = []
    uploads = []
    class Client:
        """Record bounded Slack operations without network access."""

        def member(self, user, token):
            """Return a profile with an explicit timezone.

            Keep the fixture independent from Slack account data.
            """
            return SimpleNamespace(tz="UTC")

        def upload_chart(self, png, title, token):
            """Record one private file upload.

            The returned ID belongs to the same bot used for delivery.
            """
            uploads.append(token)
            return "F_TEST"

        def call(self, method, fields, token):
            """Capture delivery identity and destination.

            No response URL is needed for the successful path.
            """
            calls.append((method, fields, token))
    view = SimpleNamespace(hours=lambda zone, day: SimpleNamespace(
        starts=[datetime(2026, 7, 15, tzinfo=UTC)], values=[5]))
    reports = SlackReports(Client(), lambda: "bot-token", view, None)
    fields = {"user_id": "U1", "channel_id": "D1", "text": "day 2026-07-15",
        "response_url": "https://hooks.slack.com/commands/test"}
    reports.execute(fields)
    reports.execute(fields)
    assert len(uploads) == 1
    assert len(calls) == 2
    assert calls[0][0] == "chat.postEphemeral"
    assert calls[0][1]["user"] == "U1"
    assert calls[0][2] == "bot-token"
