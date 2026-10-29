"""Compose runtime adapters and start the BUSY Profit collector service."""

import logging

from busy_profit.application import SalesCollectorService
from busy_profit.csv_storage import CsvHistoryRepository, HourlyCsvPublisher
from busy_profit.settings import Settings
from busy_profit.shopify import ShopifyStatsClient


def main() -> None:
    """Validate runtime settings, wire dependencies, and run the polling loop."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings()
    service = SalesCollectorService(
        settings=settings,
        source=ShopifyStatsClient(settings),
        repository=CsvHistoryRepository(settings.history_path),
        publisher=HourlyCsvPublisher(
            settings.publish_path,
            settings.display_timezone,
        ),
    )
    service.run_forever()
