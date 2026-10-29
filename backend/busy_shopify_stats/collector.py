"""Run the Shopify poller without drawing directly on a Busy Bar."""

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from busy_shopify_stats.infrastructure import BasicAuthHttpSource, CsvSalesHistoryRepository
from busy_shopify_stats.model import SalesHistoryPoint
from busy_shopify_stats.public_history import CsvHourlyHistoryPublisher
from busy_shopify_stats.representation import ShopifyStatsParser


class Settings(BaseSettings):
    """Define environment-backed settings for the history collector."""

    model_config = SettingsConfigDict(env_prefix="SHOPIFY_STATS_", case_sensitive=False)

    source_url: HttpUrl = HttpUrl("https://busy.marketing/shopifystats/count")
    basic_auth_username: str = Field(min_length=1)
    basic_auth_password: SecretStr
    polling_interval_seconds: float = Field(default=60, gt=0)
    request_timeout_seconds: float = Field(default=20, gt=0)
    display_timezone: str = "Europe/Moscow"
    history_path: Path = Path("/srv/busy-profit-feed/data/history.csv")
    publish_path: Path = Path("/srv/busy-profit-feed/public/history.csv")


def run_forever(settings: Settings) -> None:
    """Fetch and append one validated cumulative snapshot per polling interval.

    Failed source or persistence cycles are logged and retried after the normal
    interval so one transient failure does not end the collector service.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    source = BasicAuthHttpSource(
        url=str(settings.source_url),
        username=settings.basic_auth_username,
        password=settings.basic_auth_password.get_secret_value(),
        timeout_seconds=settings.request_timeout_seconds,
    )
    parser = ShopifyStatsParser()
    history = CsvSalesHistoryRepository(
        settings.history_path,
        graph_window=timedelta(days=28),
    )
    publisher = CsvHourlyHistoryPublisher(settings.publish_path, settings.display_timezone)

    while True:
        started_at = time.monotonic()
        try:
            observed_at = datetime.now(UTC)
            snapshot = parser.parse(source.fetch())
            points = history.append(
                SalesHistoryPoint(
                    observed_at=observed_at,
                    bars_sold=snapshot.bars_sold,
                    source_updated_at=snapshot.source_updated_at,
                ),
            )
            publisher.publish(points)
            logging.info(
                json.dumps(
                    {
                        "event": "sales_poll_completed",
                        "bars_sold": snapshot.bars_sold,
                        "history_points": len(points),
                    },
                ),
            )
        except Exception as error:
            logging.error(
                json.dumps(
                    {
                        "event": "sales_poll_failed",
                        "error": f"{type(error).__name__}: {error}",
                    },
                ),
            )
        elapsed = time.monotonic() - started_at
        time.sleep(max(0, settings.polling_interval_seconds - elapsed))


def main() -> None:
    """Load validated settings and start the collector lifecycle.

    Configuration errors intentionally stop startup so systemd reports a
    broken deployment rather than keeping an idle process alive.
    """
    run_forever(Settings())


if __name__ == "__main__":
    main()
