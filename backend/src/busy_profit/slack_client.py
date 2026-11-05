"""Bounded Slack Web API adapter without sensitive response logging."""

import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from busy_profit.slack_oauth import InstallationTokens


class SlackAPIError(ValueError):
    """Carry a sanitized API error code without retaining Slack response bodies."""

    def __init__(self, code: str) -> None:
        """Expose only the safe machine-readable error category.

        Callers can apply bounded retries without parsing sensitive payloads.
        """
        self.code = code
        super().__init__("Slack request failed: " + code)


class SlackMember(BaseModel):
    """Expose only membership and timezone fields needed by application services."""

    id: str
    team_id: str = ""
    deleted: bool = False
    is_bot: bool = False
    is_restricted: bool = False
    is_ultra_restricted: bool = False
    is_stranger: bool = False
    tz: str | None = None

    def eligible(self, workspace: str) -> bool:
        """Reject guests, bots, deleted accounts and external workspace members.

        Missing workspace identity fails closed rather than implying membership.
        """
        return self.team_id == workspace and not any((
            self.deleted, self.is_bot, self.is_restricted,
            self.is_ultra_restricted, self.is_stranger,
        ))


class SlackTokenResponse(BaseModel):
    """Validate an OAuth token response before accepting installation credentials."""

    access_token: str = Field(min_length=1, repr=False)
    refresh_token: str = Field(default="", repr=False)
    expires_in: int = Field(default=0, ge=0)
    team: dict[str, str] = Field(default_factory=dict)
    token_type: str


class SlackClient:
    """Own Slack protocol details, bounded network IO and token exchange."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        """Bind app credentials and a fixed redirect URI.

        Redirect destinations must never come from callback query parameters.
        """
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect = redirect_uri

    def call(self, method: str, fields: dict[str, str], token: str = "") -> dict:
        """Call a fixed Slack method and reject unsuccessful or oversized replies.

        Error messages intentionally omit raw bodies, tokens and response URLs.
        """
        if method not in {"oauth.v2.access", "users.info", "auth.test", "files.getUploadURLExternal", "files.completeUploadExternal", "chat.postEphemeral", "conversations.info", "chat.postMessage"}:
            raise ValueError("Unsupported Slack method")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if token:
            headers["Authorization"] = "Bearer " + token
        request = Request("https://slack.com/api/" + method, data=urlencode(fields).encode(), headers=headers)
        with urlopen(request, timeout=8) as response:
            body = response.read(262145)
        if len(body) > 262144:
            raise ValueError("Slack response too large")
        result = json.loads(body)
        if not isinstance(result, dict) or result.get("ok") is not True:
            allowed = {"invalid_blocks", "channel_not_found", "not_in_channel", "missing_scope", "invalid_auth", "token_expired"}
            code = result.get("error") if isinstance(result, dict) else None
            logging.getLogger("busy_profit.slack").warning("Slack API method=%s error=%s", method, code if code in allowed else "request_failed")
            raise SlackAPIError(code if code in allowed else "request_failed")
        return result

    def exchange(self, code: str) -> InstallationTokens:
        """Exchange a single-use authorization code for bot installation tokens.

        The calling service verifies the returned workspace before persistence.
        """
        response = SlackTokenResponse.model_validate(self.call("oauth.v2.access", {
            "client_id": self._client_id, "client_secret": self._client_secret,
            "code": code, "redirect_uri": self._redirect,
        }))
        if response.token_type != "bot" or not response.team.get("id"):
            raise ValueError("Expected Slack bot installation")
        return InstallationTokens(team=response.team["id"], access=response.access_token,
            refresh=response.refresh_token, expires_in=response.expires_in)

    def refresh(self, refresh_token: str) -> SlackTokenResponse:
        """Renew rotating credentials without initiating another installation.

        The caller must serialize rotation and atomically persist both tokens.
        """
        return SlackTokenResponse.model_validate(self.call("oauth.v2.access", {
            "client_id": self._client_id, "client_secret": self._client_secret,
            "grant_type": "refresh_token", "refresh_token": refresh_token,
        }))

    def member(self, user: str, token: str) -> SlackMember:
        """Fetch membership and profile timezone using the bot credential.

        Missing timezone is explicit and must not silently become server time.
        """
        return SlackMember.model_validate(self.call("users.info", {"user": user}, token)["user"])

    def upload_chart(self, data: bytes, title: str, token: str, channel: str = "") -> str:
        """Upload a private PNG and return its Slack file identifier.

        Do not publish the file to any channel or enable public URLs.
        """
        from urllib.parse import urlparse
        upload = self.call("files.getUploadURLExternal", {"filename": "profit.png", "length": str(len(data))}, token)
        url = upload["upload_url"]
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "files.slack.com":
            raise ValueError("Unexpected Slack upload destination")
        with urlopen(Request(url, data=data, headers={"Content-Type": "application/octet-stream"}), timeout=15) as response:
            response.read(1024)
        fields = {"files": json.dumps([{"id": upload["file_id"], "title": title}])}
        if channel:
            fields.update({"channel_id": channel, "initial_comment": title})
        self.call("files.completeUploadExternal", fields, token)
        return upload["file_id"]
