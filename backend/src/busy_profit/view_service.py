"""Orchestrate consistent calendar views with a bounded projection cache."""

from collections import OrderedDict
from datetime import date, datetime, timedelta
from threading import RLock
from zoneinfo import ZoneInfo

from busy_profit.calendar_views import daily_values, hourly_values, difference
from busy_profit.view_schemas import DailyView, HourlyView, ViewQuery
from busy_profit.view_storage import ObservationIndex


class RevisionChanged(ValueError):
    """Signal that a background page must restart from the current revision."""


class ViewService:
    """Keep HTTP concerns outside the projection and caching workflow."""

    def __init__(self, index: ObservationIndex, capacity: int = 128) -> None:
        """Bound cache memory across users, zones and dates.

        A lock protects the shared LRU when synchronous routes run in threads.
        """
        self._index = index
        self._capacity = capacity
        self._cache: OrderedDict[tuple[str, ...], DailyView | HourlyView] = OrderedDict()
        self._lock = RLock()

    def days(self, timezone: str, now: datetime, older: bool = False, revision: str | None = None) -> DailyView:
        """Return recent 36 days or the remaining history from launch.

        Reject mismatched revisions rather than combining inconsistent pages.
        """
        timezone = ViewQuery(timezone=timezone).timezone
        today = now.astimezone(ZoneInfo(timezone)).date()
        launch = date(2026, 7, 14)
        recent_start = max(launch, today - timedelta(days=35))
        start = launch if older else recent_start
        end = recent_start - timedelta(days=1) if older else today
        with self._lock, self._index.snapshot() as source:
            if revision is not None and revision != source.revision:
                raise RevisionChanged("Sales revision changed")
            key = ("days", source.revision, timezone, str(today), str(older))
            cached = self._cache.get(key)
            if isinstance(cached, DailyView):
                self._cache.move_to_end(key)
                return cached
            values = daily_values(source, start, max(0, (end-start).days+1), timezone)
            if not older and values:
                midnight = datetime.combine(today, datetime.min.time(), ZoneInfo(timezone))
                values[-1] = difference(source.close(midnight), source.close(now + timedelta(seconds=1)))
            result = DailyView(revision=source.revision, timezone=timezone, start=start,
                values=values,
                total=source.total, more=not older and start > launch)
            self._remember(key, result)
            return result

    def hours(self, timezone: str, day: date) -> HourlyView:
        """Return all real hours of one local calendar day.

        Cache keys include the source revision so corrections invalidate views.
        """
        timezone = ViewQuery(timezone=timezone).timezone
        with self._lock, self._index.snapshot() as source:
            key = ("hours", source.revision, timezone, str(day))
            cached = self._cache.get(key)
            if isinstance(cached, HourlyView):
                self._cache.move_to_end(key)
                return cached
            starts, values = hourly_values(source, day, timezone)
            result = HourlyView(revision=source.revision, timezone=timezone, date=day, starts=starts, values=values)
            self._remember(key, result)
            return result

    def _remember(self, key: tuple[str, ...], value: DailyView | HourlyView) -> None:
        """Insert a projection and evict the least recently used entry.

        The caller holds the service lock throughout this operation.
        """
        self._cache[key] = value
        if len(self._cache) > self._capacity:
            self._cache.popitem(last=False)
