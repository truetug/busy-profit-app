"""Persist single-use OAuth state and rotating Slack credentials."""

import hashlib
import secrets
import sqlite3
from pathlib import Path


class OAuthStorage:
    """Keep OAuth runtime secrets outside the source checkout."""

    def __init__(self, path: Path) -> None:
        """Create a private SQLite file and initialize OAuth tables.

        The deployment directory must additionally be restricted to its owner.
        """
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS oauth_states (digest TEXT PRIMARY KEY, expires INTEGER NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS slack_tokens (team TEXT PRIMARY KEY, access TEXT NOT NULL, refresh TEXT NOT NULL, expires INTEGER NOT NULL)")
        path.chmod(0o600)

    def issue_state(self, now: int) -> str:
        """Generate a short-lived opaque state and persist only its digest.

        The installation initiator must also bind it to the browser session.
        """
        state = secrets.token_urlsafe(32)
        with sqlite3.connect(self._path) as connection:
            connection.execute("DELETE FROM oauth_states WHERE expires<=?", (now,))
            connection.execute("INSERT INTO oauth_states VALUES (?,?)", (hashlib.sha256(state.encode()).hexdigest(), now + 600))
        return state

    def consume_state(self, state: str, now: int) -> bool:
        """Atomically consume a fresh state before exchanging the OAuth code.

        Replays and expired callbacks cannot trigger a second token exchange.
        """
        if not 20 <= len(state) <= 128:
            return False
        with sqlite3.connect(self._path) as connection:
            row = connection.execute(
                "DELETE FROM oauth_states WHERE digest=? AND expires>? RETURNING digest",
                (hashlib.sha256(state.encode()).hexdigest(), now),
            ).fetchone()
        return row is not None

    def save_tokens(self, team: str, access: str, refresh: str, expires: int) -> None:
        """Atomically replace installation credentials after a verified exchange.

        Plaintext tokens are necessary for API calls and rely on private storage.
        """
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "INSERT INTO slack_tokens VALUES (?,?,?,?) ON CONFLICT(team) DO UPDATE SET access=excluded.access,refresh=excluded.refresh,expires=excluded.expires",
                (team, access, refresh, expires),
            )

    def tokens(self, team: str) -> tuple[str, str, int] | None:
        """Read private installation credentials for the token manager.

        Return no credentials when the workspace has not installed the app.
        """
        with sqlite3.connect(self._path) as connection:
            return connection.execute("SELECT access,refresh,expires FROM slack_tokens WHERE team=?", (team,)).fetchone()
