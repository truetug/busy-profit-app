"""Verify HTTP security and view contracts without external services."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from busy_profit.api import create_app, shared_key_policy
from busy_profit.view_service import ViewService
from busy_profit.view_storage import ObservationIndex


def test_protected_pages_validate_timezone_and_revision(tmp_path) -> None:
    """Deny unauthenticated reads and distinguish bad queries from stale pages.

    An empty index is sufficient to exercise representation boundaries.
    """
    service = ViewService(ObservationIndex(tmp_path / "views.sqlite3"))
    app = create_app(service, shared_key_policy("test-secret"), lambda: datetime(2026, 11, 5, 12, tzinfo=UTC))
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/v1/days?timezone=UTC").status_code == 401
        headers = {"Authorization": "Bearer test-secret"}
        response = client.get("/v1/days?timezone=UTC", headers=headers)
        assert response.status_code == 200
        assert len(response.json()["values"]) == 36
        assert client.get("/v1/days?timezone=bad", headers=headers).status_code == 422
        assert client.get("/v1/days?timezone=UTC&older=true&revision=stale", headers=headers).status_code == 409
        hours = client.get("/v1/hours?date=2026-10-25&timezone=Europe/Berlin", headers=headers)
        assert hours.status_code == 200
        assert len(hours.json()["values"]) == 25
        assert client.get("/v1/hours?date=2020-01-01&timezone=UTC", headers=headers).status_code == 422
