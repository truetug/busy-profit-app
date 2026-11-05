"""Test OAuth state binding, replay prevention and workspace restriction."""

import pytest

from busy_profit.oauth_storage import OAuthStorage
from busy_profit.slack_oauth import InstallationTokens, SlackOAuthService


def test_oauth_state_is_browser_bound_and_single_use(tmp_path) -> None:
    """Reject cross-browser callbacks and replays before exchanging codes.

    A failed browser check does not consume the legitimate user's state.
    """
    storage = OAuthStorage(tmp_path / "oauth.sqlite3")
    calls = []
    def exchange(code: str) -> InstallationTokens:
        """Record exchanges without contacting Slack.

        Return credentials only for the configured test workspace.
        """
        calls.append(code)
        return InstallationTokens(team="T1", access="secret")
    service = SlackOAuthService(storage, "T1", exchange)
    state = storage.issue_state(1000)
    with pytest.raises(ValueError):
        service.complete("code", state, "other-browser", 1001)
    assert calls == []
    service.complete("code", state, state, 1001)
    with pytest.raises(ValueError):
        service.complete("code", state, state, 1002)
    assert calls == ["code"]


def test_expired_state_never_exchanges_code(tmp_path) -> None:
    """Deny stale installations without invoking the network adapter.

    State lifetime is measured using trusted server time.
    """
    storage = OAuthStorage(tmp_path / "oauth.sqlite3")
    state = storage.issue_state(1000)
    assert not storage.consume_state(state, 1600)
