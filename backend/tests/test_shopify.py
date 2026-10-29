"""Tests for Shopify Stats authentication and response handling."""

import base64
from datetime import datetime
from typing import Self, cast
from urllib.request import Request

from pydantic import SecretStr

from busy_profit.settings import Settings
from busy_profit.shopify import ShopifyStatsClient


class FakeResponse:
    """Provide the minimal response protocol consumed by urllib's adapter."""

    def __init__(self, body: bytes) -> None:
        """Store a deterministic HTTP body for a patched request call."""
        self._body = body

    def __enter__(self) -> Self:
        """Return this response from a context-managed mocked HTTP request."""
        return self

    def __exit__(self, *args: object) -> None:
        """Support the context manager contract without external resources."""

    def read(self) -> bytes:
        """Return the configured JSON response bytes."""
        return self._body


def test_client_uses_env_credentials_only_in_basic_auth_header(monkeypatch) -> None:
    """Send configured credentials in the request header and return typed data."""
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        """Capture the request and return a stable Shopify Stats response."""
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(
            b'{"ok":true,"stale":false,"products_updated_at":"2026-10-30T10:00:00Z",'
            b'"products":[{"title":"BUSY Bar","qty":7001}]}'
        )

    monkeypatch.setattr("busy_profit.shopify.urllib.request.urlopen", fake_urlopen)
    settings = Settings(
        source_url="https://example.test/stats",
        basic_auth_username="reporter",
        basic_auth_password=SecretStr("top-secret"),
    )

    count, updated_at = ShopifyStatsClient(settings).fetch_count()

    request = cast(Request, captured["request"])
    expected = base64.b64encode(b"reporter:top-secret").decode("ascii")
    assert request.get_header("Authorization") == f"Basic {expected}"
    assert "top-secret" not in repr(settings)
    assert count == 7001
    assert updated_at == datetime.fromisoformat("2026-10-30T10:00:00+00:00")
