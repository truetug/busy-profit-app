"""Project cumulative observations into fixed UTC archive buckets."""

from datetime import UTC, datetime

from busy_profit.models import SalesObservation


def hourly_utc_snapshots(
    points: list[SalesObservation],
    now: datetime,
) -> list[SalesObservation]:
    """Keep the last observation in each completed UTC hour.

    Preserve actual observation timestamps and totals so clients can compute
    their own calendar boundaries. Missing hours remain absent.
    """
    cutoff = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    latest: dict[datetime, SalesObservation] = {}
    for point in points:
        observed = point.observed_at.astimezone(UTC)
        hour = observed.replace(minute=0, second=0, microsecond=0)
        if hour < cutoff and (hour not in latest or observed > latest[hour].observed_at):
            latest[hour] = point.model_copy(update={"observed_at": observed})
    return [latest[hour] for hour in sorted(latest)]
