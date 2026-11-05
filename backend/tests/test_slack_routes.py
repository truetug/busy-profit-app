"""Check private PIN responses and OAuth transport boundaries."""

import hashlib
import hmac

from fastapi import FastAPI
from fastapi.testclient import TestClient

from busy_profit.access import AccessRepository
from busy_profit.oauth_storage import OAuthStorage
from busy_profit.slack_access import SlackAccessService
from busy_profit.slack_oauth import InstallationTokens, SlackOAuthService
from busy_profit.slack_routes import slack_router


def test_signed_command_is_private_and_installation_is_operator_only(tmp_path) -> None:
    """Protect installation initiation and return personal codes ephemerally.

    Invalid command signatures must never reach access issuance.
    """
    access = AccessRepository(tmp_path / "access.sqlite3", "p" * 32)
    storage = OAuthStorage(tmp_path / "oauth.sqlite3")
    oauth = SlackOAuthService(storage, "T1", lambda code: InstallationTokens(team="T1", access="token"))
    app = FastAPI()
    app.include_router(slack_router(SlackAccessService("secret", "T1", access, lambda user: True),
        oauth, storage, "client", "https://example.com/slack/oauth/callback", "operator", lambda: 1000))
    body = b"team_id=T1&user_id=U1&command=%2Fprofit&text=access"
    signature = "v0=" + hmac.new(b"secret", b"v0:1000:" + body, hashlib.sha256).hexdigest()
    with TestClient(app, base_url="https://example.com") as client:
        assert client.get("/slack/oauth/start").status_code == 401
        start = client.get("/slack/oauth/start", headers={"Authorization": "Bearer operator"}, follow_redirects=False)
        assert start.status_code == 303
        assert "HttpOnly" in start.headers["set-cookie"]
        assert client.post("/slack/commands", content=body).status_code == 400
        response = client.post("/slack/commands", content=body,
            headers={"X-Slack-Request-Timestamp": "1000", "X-Slack-Signature": signature})
        assert response.status_code == 200
        assert response.json()["response_type"] == "ephemeral"
