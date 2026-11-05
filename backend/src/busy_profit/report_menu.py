"""Build private Slack report controls without transport or storage logic."""

from datetime import date


def report_menu(today: date, timezone: str) -> dict:
    """Present period selection privately with visible timezone context.

    Buttons request reports; channel publication is a separate confirmed action.
    """
    return {
        "response_type": "ephemeral",
        "text": "BUSY Profit",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "BUSY Profit"}},
            {"type": "context", "elements": [{"type": "plain_text", "text": f"Personal timezone: {timezone} · Channel reports: UTC"}]},
            {"type": "actions", "elements": [
                {"type": "datepicker", "action_id": "profit_day", "initial_date": today.isoformat(), "placeholder": {"type": "plain_text", "text": "Choose a day"}},
                {"type": "button", "action_id": "profit_today", "text": {"type": "plain_text", "text": "Today"}},
                {"type": "button", "action_id": "profit_month", "text": {"type": "plain_text", "text": "Selected month"}},
                {"type": "button", "action_id": "profit_access", "text": {"type": "plain_text", "text": "Get Bar PIN"}},
            ]},
        ],
    }
