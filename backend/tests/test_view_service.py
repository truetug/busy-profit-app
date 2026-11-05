"""Verify revision consistency and cache invalidation."""

from datetime import UTC, datetime

import pytest

from busy_profit.models import SalesObservation
from busy_profit.view_service import RevisionChanged, ViewService
from busy_profit.view_storage import ObservationIndex


def test_reimport_is_stable_but_correction_invalidates_pages(tmp_path) -> None:
    """Repeated source imports retain a revision, corrections replace it.

    A background page may never silently mix revisions with the first page.
    """
    index = ObservationIndex(tmp_path / "sales.sqlite3")
    at = datetime(2026, 11, 4, 23, 59, tzinfo=UTC)
    point = SalesObservation(observed_at=at, source_updated_at=at, bars_sold=5000)
    index.import_points([point])
    service = ViewService(index)
    now = datetime(2026, 11, 5, 12, tzinfo=UTC)
    first = service.days("UTC", now)
    assert len(first.values) == 36
    assert first.more
    index.import_points([point])
    assert service.days("UTC", now) is first
    older = service.days("UTC", now, older=True, revision=first.revision)
    assert not older.more
    index.import_points([point.model_copy(update={"bars_sold": 5001})])
    with pytest.raises(RevisionChanged):
        service.days("UTC", now, older=True, revision=first.revision)
    assert service.days("UTC", now).total == 5001
