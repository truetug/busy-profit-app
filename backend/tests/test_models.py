"""Tests for validating and mapping Shopify source payloads."""

import pytest

from busy_profit.models import ShopifyStatsResponse


def test_busy_bar_count_matches_title_without_case_or_whitespace_sensitivity() -> None:
    """Accept one matching product despite casing and repeated whitespace."""
    payload = ShopifyStatsResponse.model_validate(
        {
            "ok": True,
            "stale": False,
            "products_updated_at": "2026-10-30T10:00:00Z",
            "products": [
                {"title": "  BUSY   Bar ", "qty": 1234},
                {"title": "Other Product", "qty": 8},
            ],
        },
    )

    assert payload.busy_bar_count() == 1234


@pytest.mark.parametrize(
    ("products", "ok", "stale", "message"),
    [
        ([], True, False, "exactly one"),
        (
            [{"title": "BUSY Bar", "qty": 1}, {"title": "Busy Bar", "qty": 2}],
            True,
            False,
            "exactly one",
        ),
        ([{"title": "BUSY Bar", "qty": 1}], False, False, "neither fresh nor stale"),
    ],
)
def test_busy_bar_count_rejects_ambiguous_or_unusable_payloads(
    products: list[dict[str, str | int]],
    ok: bool,
    stale: bool,
    message: str,
) -> None:
    """Reject missing, duplicate, or explicitly unusable source data."""
    payload = ShopifyStatsResponse.model_validate(
        {
            "ok": ok,
            "stale": stale,
            "products_updated_at": "2026-10-30T10:00:00Z",
            "products": products,
        },
    )

    with pytest.raises(ValueError, match=message):
        payload.busy_bar_count()
