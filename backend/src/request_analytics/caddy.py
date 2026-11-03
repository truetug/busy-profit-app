"""Map untrusted Caddy access records into validated usage events."""

import json
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit

from pydantic import ValidationError

from request_analytics.models import UsageEvent
from request_analytics.profile import AnalyticsProfile


def parse_usage_line(line: bytes, profile: AnalyticsProfile) -> UsageEvent | None:
    """Extract supported feed requests and ignore malformed or unrelated input.

    Use the socket peer IP only; client headers never select the source address.
    """
    try:
        record = json.loads(line)
        request = record["request"]
        endpoint = urlsplit(request["uri"]).path
        if endpoint not in profile.endpoints or request.get("method") not in {"GET", "HEAD"}:
            return None
        headers = request.get("headers", {})
        values = next((value for key, value in headers.items() if key.lower() == profile.device_header.lower()), [])
        uid = values[0] if isinstance(values, list) and len(values) == 1 and isinstance(values[0], str) else ""
        if profile.uppercase_device_id:
            uid = uid.upper()
        if not re.fullmatch(profile.device_pattern, uid):
            uid = ""
        telemetry: dict[str, str | int] = {}
        normalized = {key.lower(): value for key, value in headers.items()}
        session = normalized.get(profile.session_header.lower(), [""])[0]
        try:
            uptime = int(normalized.get(profile.uptime_header.lower(), ["0"])[0])
            details = int(normalized.get(profile.details_header.lower(), ["0"])[0])
            if isinstance(session, str) and re.fullmatch(r"[a-zA-Z0-9-]{8,64}", session) and 0 <= uptime <= 31536000 and 0 <= details <= 1000000:
                telemetry = {"session_id": session, "uptime_seconds": uptime, "details_count": details}
        except (ValueError, TypeError, IndexError):
            pass
        return UsageEvent(
            at=datetime.fromtimestamp(record["ts"], UTC),
            hardware_id=uid,
            endpoint=endpoint,
            status=record["status"],
            ip=request["remote_ip"],
            **telemetry,
        )
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, ValidationError):
        return None
