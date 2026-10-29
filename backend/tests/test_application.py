"""Tests for the sales polling use-case orchestration."""

from datetime import UTC, datetime
from pathlib import Path

from busy_profit.application import SalesCollectorService
from busy_profit.models import SalesObservation
from busy_profit.settings import Settings


class FakeSource:
    """Return a deterministic sales count through the source port."""

    def fetch_count(self) -> tuple[int, datetime]:
        """Provide a fixed count and source timestamp for one poll."""
        return 88, datetime(2026, 10, 30, 10, tzinfo=UTC)


class FakeRepository:
    """Capture the observation and return it as retained history."""

    def __init__(self) -> None:
        """Initialize the repository's captured observation state."""
        self.saved: SalesObservation | None = None

    def save(self, point: SalesObservation) -> list[SalesObservation]:
        """Keep the point and expose it as the full retained history."""
        self.saved = point
        return [point]


class FakePublisher:
    """Capture each public history projection request."""

    def __init__(self) -> None:
        """Initialize the publisher's captured points state."""
        self.published: list[SalesObservation] = []

    def publish(self, points: list[SalesObservation]) -> None:
        """Keep the projected points for assertions."""
        self.published = points


def test_poll_once_runs_source_repository_and_publisher_in_order() -> None:
    """Build one domain observation and pass it through both output ports."""
    settings = Settings(
        source_url="https://example.test/stats",
        basic_auth_username="reporter",
        basic_auth_password="not-logged",
        history_path=Path("/tmp/history.csv"),
        publish_path=Path("/tmp/public.csv"),
    )
    repository = FakeRepository()
    publisher = FakePublisher()
    service = SalesCollectorService(settings, FakeSource(), repository, publisher)

    point = service.poll_once()

    assert point.bars_sold == 88
    assert point.source_updated_at == datetime(2026, 10, 30, 10, tzinfo=UTC)
    assert repository.saved == point
    assert publisher.published == [point]
