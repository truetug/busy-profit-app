"""Validation and mapping for the Shopify Stats JSON representation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from busy_shopify_stats.model import SalesSnapshot


class SourceProduct(BaseModel):
    """Represent one product row returned by the Shopify Stats endpoint.

    Extra source fields remain ignored so harmless endpoint additions do not
    break the polling service.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    qty: int = Field(ge=0)


class SourceResponse(BaseModel):
    """Represent the relevant validated subset of the source JSON response.

    Both fresh and explicitly stale payloads are accepted by the service, while
    an unsuccessful non-stale payload is rejected.
    """

    model_config = ConfigDict(extra="ignore")

    ok: bool = False
    stale: bool = False
    products: list[SourceProduct]
    products_updated_at: datetime


class ShopifyStatsParser:
    """Map the source transport model into the internal sales snapshot.

    Product matching is normalized for case and surrounding whitespace while
    retaining an unambiguous single canonical product name.
    """

    def __init__(self, product_title: str = "BUSY Bar") -> None:
        """Configure the canonical product title expected in source payloads.

        Normalization is performed once and reused for every polling cycle.
        """
        self._normalized_product_title = self._normalize_title(product_title)

    def parse(self, payload: bytes) -> SalesSnapshot:
        """Validate one JSON payload and extract the cumulative Busy Bar count.

        Missing, duplicated, or unsuccessful product data is rejected so an
        invalid source response cannot overwrite the last good state.
        """
        response = SourceResponse.model_validate_json(payload)
        if not response.ok and not response.stale:
            raise ValueError("Shopify Stats response is neither fresh nor stale")

        products = [
            product
            for product in response.products
            if self._normalize_title(product.title) == self._normalized_product_title
        ]
        if len(products) != 1:
            raise ValueError("Shopify Stats response must contain exactly one BUSY Bar product")

        return SalesSnapshot(
            bars_sold=products[0].qty,
            source_updated_at=response.products_updated_at,
        )

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize a source product title for stable exact-name matching.

        Repeated whitespace and case differences are treated as presentation
        details rather than different product identities.
        """
        return " ".join(title.casefold().split())

