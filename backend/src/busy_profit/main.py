"""Compose runtime adapters and start the BUSY Profit collector service."""

import logging
from pathlib import Path

from busy_profit.application import SalesCollectorService
from busy_profit.csv_storage import CsvHistoryRepository, DisplayHistoryCsvPublisher
from busy_profit.landing import LandingPublisher
from busy_profit.settings import Settings
from busy_profit.shopify import ShopifyStatsClient


def main() -> None:
    """Publish the landing and start collection, even if publication fails.

    Wire the application service and infrastructure from validated settings.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings()
    try:
        LandingPublisher(Path("/app/landing"), settings.publish_path.parent / "landing").publish()
    except (OSError, ValueError) as error:
        logging.getLogger("busy_profit").warning("Landing publication failed: %s", type(error).__name__)
    service = SalesCollectorService(
        settings=settings,
        source=ShopifyStatsClient(settings),
        repository=CsvHistoryRepository(settings.history_path),
        publisher=DisplayHistoryCsvPublisher(
            settings.publish_path,
            settings.display_timezone,
        ),
    )
    service.run_forever()
