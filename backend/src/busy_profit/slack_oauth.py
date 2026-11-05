"""Orchestrate OAuth code exchange through an injected Slack adapter."""

from collections.abc import Callable
from hmac import compare_digest

from pydantic import BaseModel, Field

from busy_profit.oauth_storage import OAuthStorage


class InstallationTokens(BaseModel):
    """Represent validated installation tokens, not an untrusted Slack payload."""

    team: str
    access: str = Field(repr=False, min_length=1)
    refresh: str = Field(default="", repr=False)
    expires_in: int = Field(default=0, ge=0)


class SlackOAuthService:
    """Bind OAuth callbacks to the installing browser and expected workspace."""

    def __init__(self, storage: OAuthStorage, team: str, exchange: Callable[[str], InstallationTokens]) -> None:
        """Inject private storage and a bounded network exchange adapter.

        Never let the callback select the trusted workspace or redirect URL.
        """
        self._storage = storage
        self._team = team
        self._exchange = exchange

    def complete(self, code: str, state: str, browser_state: str, now: int) -> None:
        """Validate browser binding and single-use state before exchanging code.

        Store credentials only after checking the returned installation identity.
        """
        if not code or len(code) > 1024 or not state or not compare_digest(state, browser_state):
            raise ValueError("Invalid OAuth callback")
        if not self._storage.consume_state(state, now):
            raise ValueError("OAuth state expired or already used")
        tokens = self._exchange(code)
        if not self._team or tokens.team != self._team:
            raise PermissionError("Unexpected Slack workspace")
        self._storage.save_tokens(tokens.team, tokens.access, tokens.refresh, now + tokens.expires_in if tokens.expires_in else 0)
