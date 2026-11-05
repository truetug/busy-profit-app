"""Validate Slack command requests and orchestrate personal access issuance."""

import hashlib
import hmac
from collections.abc import Callable
from urllib.parse import parse_qs

from busy_profit.access import AccessRepository


class SlackAccessService:
    """Issue credentials only for signed, authorized workspace members."""

    def __init__(self, signing_secret: str, workspace: str, access: AccessRepository, eligible: Callable[[str], bool]) -> None:
        """Inject verified membership policy separately from request transport.

        The membership adapter must reject guests, external and deleted users.
        """
        self._secret = signing_secret.encode()
        self._workspace = workspace
        self._access = access
        self._eligible = eligible

    def execute(self, body: bytes, timestamp: str, signature: str, now: int) -> str:
        """Verify the unmodified request body before parsing its command.

        Reject stale requests and never trust workspace or user IDs unsigned.
        """
        if not self._secret or not self._workspace or len(body) > 16384:
            raise ValueError("Slack access unavailable")
        try:
            age = abs(now - int(timestamp))
        except ValueError as error:
            raise ValueError("Invalid Slack signature") from error
        expected = "v0=" + hmac.new(self._secret, b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
        if age > 300 or not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid Slack signature")
        fields = parse_qs(body.decode("utf-8"), strict_parsing=True)
        def field(name: str) -> str:
            """Read a single field, rejecting duplicate identity parameters.

            Missing fields are invalid rather than inferred from other inputs.
            """
            values = fields.get(name, [])
            if len(values) != 1:
                raise ValueError("Invalid Slack command")
            return values[0]
        user = field("user_id")
        if field("team_id") != self._workspace or field("command") != "/profit" or field("text").strip() != "access":
            raise ValueError("Unsupported Slack command")
        if not self._eligible(user):
            raise PermissionError("Access is limited to approved employees")
        return self._access.issue(self._workspace, user)
