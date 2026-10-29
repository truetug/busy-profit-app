"""Poll Shopify Stats, retain minute history, and publish the hourly view."""

import base64
import csv
import json
import logging
import os
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load the collector's credentials and runtime paths from its environment."""

    model_config = SettingsConfigDict(env_prefix="SHOPIFY_STATS_", case_sensitive=False)

    source_url: HttpUrl = HttpUrl("https://busy.marketing/shopifystats/count")
    basic_auth_username: str = Field(min_length=1)
    basic_auth_password: SecretStr
    polling_interval_seconds: float = Field(default=60, gt=0)
    request_timeout_seconds: float = Field(default=20, gt=0)
    display_timezone: str = "Europe/Moscow"
    history_path: Path = Path("/data/history.csv")
    publish_path: Path = Path("/data/public/history.csv")


class Product(BaseModel):
    """Validate the product fields needed from the Shopify Stats response."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    qty: int = Field(ge=0)


class SourceResponse(BaseModel):
    """Validate the useful portion of one Shopify Stats response."""

    model_config = ConfigDict(extra="ignore")

    ok: bool = False
    stale: bool = False
    products: list[Product]
    products_updated_at: datetime


class HistoryPoint(BaseModel):
    """Represent one timestamped cumulative sales observation."""

    observed_at: datetime
    bars_sold: int = Field(ge=0)
    source_updated_at: datetime


FIELDNAMES = ("observed_at", "bars_sold", "source_updated_at")
LOG = logging.getLogger("busy_profit_collector")


def fetch_count(settings: Settings) -> tuple[int, datetime]:
    """Request the source and return the unique BUSY Bar count and update time.

    Basic Auth stays in the request header; invalid, stale-unknown, or ambiguous
    responses are rejected so they cannot alter the saved history.
    """
    credentials = f"{settings.basic_auth_username}:{settings.basic_auth_password.get_secret_value()}"
    authorization = base64.b64encode(credentials.encode()).decode("ascii")
    request = urllib.request.Request(
        str(settings.source_url),
        headers={
            "Authorization": f"Basic {authorization}",
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "busy-profit-collector/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=settings.request_timeout_seconds) as response:
        payload = SourceResponse.model_validate_json(response.read())

    if not payload.ok and not payload.stale:
        raise ValueError("Shopify Stats response is neither fresh nor stale")
    products = [
        product
        for product in payload.products
        if " ".join(product.title.casefold().split()) == "busy bar"
    ]
    if len(products) != 1:
        raise ValueError("Shopify Stats must contain exactly one BUSY Bar product")
    return products[0].qty, payload.products_updated_at


def read_history(path: Path) -> list[HistoryPoint]:
    """Load and validate a CSV history file in chronological order.

    A missing file is an empty first-run history; a malformed schema is an
    explicit error rather than silently discarded sales data.
    """
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDNAMES:
            raise ValueError(f"invalid sales history CSV header: {path}")
        points = [HistoryPoint.model_validate(row) for row in reader]
    return sorted(points, key=lambda point: point.observed_at)


def csv_row(point: HistoryPoint) -> dict[str, str | int]:
    """Map one observation to the stable, flat CSV representation.

    ISO-8601 timestamps keep offsets intact while remaining spreadsheet-friendly.
    """
    return {
        "observed_at": point.observed_at.isoformat(),
        "bars_sold": point.bars_sold,
        "source_updated_at": point.source_updated_at.isoformat(),
    }


def rewrite_history(path: Path, points: list[HistoryPoint]) -> None:
    """Atomically replace the rolling history after its daily retention prune."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(csv_row(point) for point in points)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def append_point(path: Path, point: HistoryPoint) -> None:
    """Append and flush one observation, creating the CSV header if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(csv_row(point))
        stream.flush()
        os.fsync(stream.fileno())


def save_observation(settings: Settings, point: HistoryPoint) -> list[HistoryPoint]:
    """Update rolling and monthly CSVs and return the retained graph history.

    The rolling file is pruned to 28 days, while calendar-month archives are
    append-only and remain available for future history or display changes.
    """
    cutoff = point.observed_at - timedelta(days=28)
    existing = read_history(settings.history_path)
    retained = [item for item in existing if item.observed_at >= cutoff]
    crossed_day = bool(existing) and existing[-1].observed_at.date() != point.observed_at.date()
    if len(retained) != len(existing) or crossed_day:
        rewrite_history(
            settings.history_path,
            retained,
        )

    append_point(settings.history_path, point)
    monthly_path = settings.history_path.with_name(
        f"history-{point.observed_at:%Y-%m}.csv",
    )
    append_point(monthly_path, point)
    return [item for item in read_history(settings.history_path) if item.observed_at >= cutoff]


def publish_hourly(settings: Settings, points: list[HistoryPoint]) -> None:
    """Atomically publish the latest cumulative observation from every local hour."""
    timezone = ZoneInfo(settings.display_timezone)
    by_hour: dict[datetime, HistoryPoint] = {}
    for point in points:
        local_time = point.observed_at.astimezone(timezone)
        hour = local_time.replace(minute=0, second=0, microsecond=0)
        by_hour[hour] = point

    path = settings.publish_path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(
            csv_row(point)
            for point in sorted(by_hour.values(), key=lambda item: item.observed_at)
        )
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_forever(settings: Settings) -> None:
    """Poll once per configured interval and retry transient failures.

    Network, parsing, or file errors are logged without terminating the service.
    """
    while True:
        started_at = time.monotonic()
        try:
            count, source_updated_at = fetch_count(settings)
            point = HistoryPoint(
                observed_at=datetime.now(UTC),
                bars_sold=count,
                source_updated_at=source_updated_at,
            )
            history = save_observation(settings, point)
            publish_hourly(settings, history)
            LOG.info(
                json.dumps(
                    {"event": "sales_poll_completed", "bars_sold": count, "history_points": len(history)},
                ),
            )
        except Exception as error:
            LOG.error(
                json.dumps({"event": "sales_poll_failed", "error": f"{type(error).__name__}: {error}"}),
            )
        time.sleep(max(0, settings.polling_interval_seconds - (time.monotonic() - started_at)))


def main() -> None:
    """Validate runtime settings and start the long-running polling loop.

    Invalid credentials or paths fail at startup so Compose shows a clear error.
    """
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_forever(Settings())


if __name__ == "__main__":
    main()
