"""Tests for required collector environment configuration."""

import pytest
from pydantic import ValidationError

from busy_profit.settings import Settings


def test_settings_require_source_url_and_both_basic_auth_values(monkeypatch) -> None:
    """Fail configuration validation instead of silently using source defaults."""
    for key in (
        "SHOPIFY_STATS_SOURCE_URL",
        "SHOPIFY_STATS_BASIC_AUTH_USERNAME",
        "SHOPIFY_STATS_BASIC_AUTH_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)

    assert {item["loc"][0] for item in error.value.errors()} == {
        "source_url",
        "basic_auth_username",
        "basic_auth_password",
    }
