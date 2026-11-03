"""Map untrusted Caddy access records into validated usage events."""

import json
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import ValidationError

from busy_profit.usage_models import UsageEvent

FEEDS = frozenset({"/current.csv", "/older.csv", "/history.csv"})


def parse_usage_line(line: bytes) -> UsageEvent | None:
    """Extract supported feed requests and ignore malformed or unrelated input.

    Use the socket peer IP only; client headers never select the source address.
    """
    try:
        record = json.loads(line)
        request = record["request"]
        endpoint = urlsplit(request["uri"]).path
        if endpoint not in FEEDS or request.get("method") not in {"GET", "HEAD"}:
            return None
        headers = request.get("headers", {})
        values = next((value for key, value in headers.items() if key.lower() == "x-busy-hardware-id"), [])
        uid = values[0].upper() if isinstance(values, list) and len(values) == 1 and isinstance(values[0], str) else ""
        if not re.fullmatch(r"[0-9A-F]{24}", uid):
            uid = ""
        return UsageEvent(
            at=datetime.fromtimestamp(record["ts"], UTC),
            hardware_id=uid,
            endpoint=endpoint,
            status=record["status"],
            ip=request["remote_ip"],
        )
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, ValidationError):
        return None
