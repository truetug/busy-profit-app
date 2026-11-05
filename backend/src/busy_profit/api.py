"""Represent compact sales views through authenticated HTTP endpoints."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from hmac import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import ValidationError

from busy_profit.view_schemas import DailyView, HourlyView
from busy_profit.view_service import RevisionChanged, ViewService


def create_app(
    service: ViewService,
    authorize: Callable[[str], bool],
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    """Compose representation with injected use cases and credential policy.

    Authorization is replaceable by the personal-access repository without
    coupling routes to SQLite or Slack.
    """
    app = FastAPI(title="BUSY Profit API", docs_url=None, redoc_url=None, openapi_url=None)

    def require_access(authorization: str | None = Header(default=None)) -> None:
        """Validate a bounded bearer credential before accessing sales.

        Keep credentials out of errors and never accept query-string secrets.
        """
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Access required")
        token = authorization[7:]
        if not 1 <= len(token) <= 256 or not authorize(token):
            raise HTTPException(401, "Access required")

    @app.get("/health/live")
    def health() -> dict[str, str]:
        """Expose process liveness without data or credentials.

        Storage readiness is verified separately during deployment.
        """
        return {"status": "ok"}

    @app.get("/v1/days", response_model=DailyView, dependencies=[Depends(require_access)])
    def days(
        timezone: str = Query(max_length=64),
        older: bool = False,
        revision: str | None = Query(default=None, max_length=32),
    ) -> DailyView:
        """Return a bounded daily page from the application service.

        Translate validation and consistency failures into explicit HTTP errors.
        """
        try:
            return service.days(timezone, clock(), older, revision)
        except RevisionChanged as error:
            raise HTTPException(409, "Revision changed; reload recent days") from error
        except ValidationError as error:
            raise HTTPException(422, "Unsupported timezone") from error

    @app.get("/v1/hours", response_model=HourlyView, dependencies=[Depends(require_access)])
    def hours(
        date: date,
        timezone: str = Query(max_length=64),
    ) -> HourlyView:
        """Return the selected day's real chronological hour buckets.

        Restrict dates to the supported selling period before storage access.
        """
        if date < datetime(2026, 7, 14).date() or date > clock().date():
            raise HTTPException(422, "Date outside available range")
        try:
            return service.hours(timezone, date)
        except ValidationError as error:
            raise HTTPException(422, "Unsupported timezone") from error

    return app


def shared_key_policy(key: str) -> Callable[[str], bool]:
    """Provide a transitional shared-key policy with constant-time comparison.

    Empty configuration always denies access rather than enabling public data.
    """
    def authorize(token: str) -> bool:
        """Check the temporary shared key without leaking comparison prefixes.

        Personal credentials will replace this policy at composition time.
        """
        return bool(key) and compare_digest(token.encode(), key.encode())
    return authorize
