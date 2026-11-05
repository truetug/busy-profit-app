"""Check explicit timezone validation at the API boundary."""

import pytest
from pydantic import ValidationError

from busy_profit.view_schemas import ViewQuery


def test_named_timezones_include_dst_and_fractional_offsets() -> None:
    """Accept names carrying full calendar rules.

    Both DST regions and fractional-hour zones must remain representable.
    """
    for name in ["Europe/Berlin", "Asia/Kolkata", "Asia/Kathmandu", "UTC"]:
        assert ViewQuery(timezone=name).timezone == name


def test_unknown_timezone_does_not_fall_back_to_server_time() -> None:
    """Reject unknown names instead of silently changing daily totals.

    Missing timezone context is rejected at the same boundary.
    """
    for payload in [{}, {"timezone": "not-a-zone"}]:
        with pytest.raises(ValidationError):
            ViewQuery.model_validate(payload)
