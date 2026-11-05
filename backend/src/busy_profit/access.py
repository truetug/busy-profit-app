"""Persist revocable personal access codes without storing their plaintext."""

import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path


class AccessRepository:
    """Bind one active credential to each verified Slack identity."""

    def __init__(self, path: Path, pepper: str) -> None:
        """Configure a server-side HMAC secret and create the access table.

        The pepper belongs in runtime secrets and must survive restarts.
        """
        if len(pepper) < 32:
            raise ValueError("Access pepper must contain at least 32 characters")
        self._path = path
        self._pepper = pepper.encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS access_codes (workspace TEXT NOT NULL, user TEXT NOT NULL, digest TEXT NOT NULL UNIQUE, issued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(workspace,user))")

    def _digest(self, code: str) -> str:
        """Derive the lookup value without exposing the original credential.

        Normalize only generated presentation separators and letter case.
        """
        normalized = code.strip().replace("-", "").upper()
        return hmac.new(self._pepper, normalized.encode(), hashlib.sha256).hexdigest()

    def issue(self, workspace: str, user: str) -> str:
        """Rotate the user's code atomically and return plaintext only once.

        Previous codes stop authorizing immediately after the transaction.
        """
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "".join(secrets.choice(alphabet) for _ in range(16))
        with sqlite3.connect(self._path) as connection:
            connection.execute(
                "INSERT INTO access_codes(workspace,user,digest) VALUES (?,?,?) ON CONFLICT(workspace,user) DO UPDATE SET digest=excluded.digest, issued_at=CURRENT_TIMESTAMP",
                (workspace, user, self._digest(code)),
            )
        return "-".join(code[index:index+4] for index in range(0, 16, 4))

    def authorize(self, code: str) -> bool:
        """Resolve a bounded credential against the active-code table.

        Unknown and revoked codes follow the same lookup path.
        """
        if not 4 <= len(code) <= 256:
            return False
        with sqlite3.connect(self._path) as connection:
            return connection.execute("SELECT 1 FROM access_codes WHERE digest=?", (self._digest(code),)).fetchone() is not None

    def seed_shared(self, code: str) -> None:
        """Store the transitional shared PIN as a separate system principal.

        Personal issuance cannot replace or inherit this explicitly named entry.
        """
        if not code:
            return
        with sqlite3.connect(self._path) as connection:
            connection.execute("INSERT INTO access_codes(workspace,user,digest) VALUES ('system','shared',?) ON CONFLICT(workspace,user) DO UPDATE SET digest=excluded.digest", (self._digest(code),))

    def owner(self, code: str) -> tuple[str, str] | None:
        """Resolve an active credential to its private stable identity.

        Revoked credentials resolve to no owner and cannot create usage events.
        """
        if not 4 <= len(code) <= 256:
            return None
        with sqlite3.connect(self._path) as connection:
            return connection.execute("SELECT workspace,user FROM access_codes WHERE digest=?", (self._digest(code),)).fetchone()

    def revoke(self, workspace: str, user: str) -> None:
        """Remove a user's active access without modifying sales data.

        Revoking an already absent user is intentionally idempotent.
        """
        with sqlite3.connect(self._path) as connection:
            connection.execute("DELETE FROM access_codes WHERE workspace=? AND user=?", (workspace, user))
