"""Run the private hourly access-log importer independently of sales polling."""

import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from busy_profit.usage_application import import_usage_logs
from busy_profit.usage_storage import UsageRepository


class AnalyticsSettings(BaseSettings):
    """Validate worker-only runtime paths and import/retention policy."""

    model_config = SettingsConfigDict(env_prefix="BUSY_USAGE_")
    log_directory: Path = Path("/logs")
    database_path: Path = Path("/data/usage.sqlite3")
    interval_seconds: float = Field(default=3600, gt=0)
    retention_days: int = Field(default=90, ge=8)


def main() -> None:
    """Import immediately after startup and retry hourly without logging identities.

    A separate process keeps log ingestion failures away from sales collection.
    """
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = AnalyticsSettings()
    while True:
        repository = None
        try:
            repository = UsageRepository(settings.database_path)
            count = import_usage_logs(settings.log_directory, repository)
            repository.prune(datetime.now(UTC), settings.retention_days)
            logging.info("usage_import_completed records=%s", count)
        except Exception as error:
            logging.error("usage_import_failed error=%s", type(error).__name__)
        finally:
            if repository is not None:
                repository.close()
        time.sleep(settings.interval_seconds)


if __name__ == "__main__":
    main()
