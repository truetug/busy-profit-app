"""Shopify Stats HTTP adapter and response-to-domain mapping."""

import base64
import urllib.request
from datetime import datetime

from busy_profit.models import ShopifyStatsResponse
from busy_profit.settings import Settings


class ShopifyStatsClient:
    """Fetch and validate BUSY Bar counts from the configured Shopify Stats URL."""

    def __init__(self, settings: Settings) -> None:
        """Retain source connection settings without exposing secret values."""
        self._settings = settings

    def fetch_count(self) -> tuple[int, datetime]:
        """Request the JSON source and map its unique BUSY Bar product to a count."""
        credentials = (
            f"{self._settings.basic_auth_username}:"
            f"{self._settings.basic_auth_password.get_secret_value()}"
        )
        authorization = base64.b64encode(credentials.encode()).decode("ascii")
        request = urllib.request.Request(
            str(self._settings.source_url),
            headers={
                "Authorization": f"Basic {authorization}",
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "busy-profit-app-backend/1.0",
            },
        )
        with urllib.request.urlopen(
            request,
            timeout=self._settings.request_timeout_seconds,
        ) as response:
            payload = ShopifyStatsResponse.model_validate_json(response.read())
        return payload.busy_bar_count(), payload.products_updated_at
