"""Exercise personal-code lifecycle and Slack request verification."""

import hashlib
import hmac

import pytest

from busy_profit.access import AccessRepository
from busy_profit.slack_access import SlackAccessService


def test_rotation_revocation_and_no_plaintext_storage(tmp_path) -> None:
    """Rotating or revoking credentials immediately removes old access.

    SQLite contents must never contain the presented credential.
    """
    path = tmp_path / "access.sqlite3"
    repository = AccessRepository(path, "x" * 32)
    first = repository.issue("T1", "U1")
    assert repository.authorize(first)
    second = repository.issue("T1", "U1")
    assert not repository.authorize(first)
    assert repository.authorize(second)
    assert second.replace("-", "").encode() not in path.read_bytes()
    repository.revoke("T1", "U1")
    assert not repository.authorize(second)


def test_slack_requires_signature_freshness_and_employee_policy(tmp_path) -> None:
    """Signed identity alone is insufficient without membership approval.

    Invalid signatures, stale requests and guests cannot receive credentials.
    """
    repository = AccessRepository(tmp_path / "access.sqlite3", "p" * 32)
    secret = "signing-secret"
    body = b"team_id=T1&user_id=U1&command=%2Fprofit&text=access"
    signature = "v0=" + hmac.new(secret.encode(), b"v0:1000:" + body, hashlib.sha256).hexdigest()
    service = SlackAccessService(secret, "T1", repository, lambda user: user == "U1")
    code = service.execute(body, "1000", signature, 1001)
    assert repository.authorize(code)
    with pytest.raises(ValueError):
        service.execute(body, "1000", signature, 1400)
    with pytest.raises(ValueError):
        service.execute(body + b"x", "1000", signature, 1001)
    denied = SlackAccessService(secret, "T1", repository, lambda user: False)
    with pytest.raises(PermissionError):
        denied.execute(body, "1000", signature, 1001)
