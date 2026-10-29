"""Domain models and revenue rules for Busy Bar sales statistics."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SalesSnapshot(BaseModel):
    """Represent one validated observation of cumulative Busy Bar sales.

    The snapshot is independent from the source JSON and can be persisted as the
    stable internal state of the polling service.
    """

    model_config = ConfigDict(frozen=True)

    bars_sold: int = Field(ge=0)
    source_updated_at: datetime


class SalesTransition(BaseModel):
    """Describe the previous and current values for one display cycle.

    A missing previous snapshot marks the initial baseline and must not be
    rendered as a fabricated zero-to-current sales change.
    """

    model_config = ConfigDict(frozen=True)

    previous: SalesSnapshot | None
    current: SalesSnapshot
    previous_revenue_usd: int | None
    current_revenue_usd: int


class RevenuePolicy(BaseModel):
    """Calculate cumulative revenue using the agreed two-tier USD pricing.

    Whole dollars are used because both tariff values are integral and no
    floating-point arithmetic is needed.
    """

    model_config = ConfigDict(frozen=True)

    subsequent_price_start: int = Field(default=3000, gt=0)
    initial_price_usd: int = Field(default=199, ge=0)
    subsequent_price_usd: int = Field(default=249, ge=0)

    def calculate(self, bars_sold: int) -> int:
        """Return cumulative revenue for a non-negative number of sold bars.

        Units before the configured boundary use the initial price. The unit at
        the boundary and every later unit use the subsequent price.
        """
        if bars_sold < 0:
            raise ValueError("bars_sold must not be negative")

        initial_unit_limit = self.subsequent_price_start - 1
        initial_units = min(bars_sold, initial_unit_limit)
        subsequent_units = max(bars_sold - initial_unit_limit, 0)
        return (
            initial_units * self.initial_price_usd
            + subsequent_units * self.subsequent_price_usd
        )


class SalesHistoryPoint(BaseModel):
    """Represent one minute-level observation used for the background chart.

    Observation time belongs to the local polling workflow while source time
    preserves when Shopify last refreshed the product aggregate.
    """

    model_config = ConfigDict(frozen=True)

    observed_at: datetime
    bars_sold: int = Field(ge=0)
    source_updated_at: datetime


class DisplaySchedule(BaseModel):
    """Decide whether a changed sales count requires a display.

    Polling and minute-history recording continue independently, while the
    screen is touched only when the cumulative bar count changes.
    """

    model_config = ConfigDict(frozen=True)

    def should_display(
        self,
        previous_bars_sold: int | None,
        current_bars_sold: int,
    ) -> bool:
        """Return whether the current count differs from the display baseline.

        Missing display state is a baseline bootstrap and does not render a
        fabricated startup event. Downward source corrections are shown because
        the visible statistic changed.
        """
        return (
            previous_bars_sold is not None
            and current_bars_sold != previous_bars_sold
        )
