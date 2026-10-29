"""Typed domain objects shared by the collector application and adapters."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShopifyProduct(BaseModel):
    """Represent one product row returned by Shopify Stats."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    qty: int = Field(ge=0)


class ShopifyStatsResponse(BaseModel):
    """Validate the source response fields used by sales collection."""

    model_config = ConfigDict(extra="ignore")

    ok: bool = False
    stale: bool = False
    products: list[ShopifyProduct]
    products_updated_at: datetime

    def busy_bar_count(self) -> int:
        """Return the unique BUSY Bar quantity or reject an ambiguous payload."""
        if not self.ok and not self.stale:
            raise ValueError("Shopify Stats response is neither fresh nor stale")

        products = [
            product
            for product in self.products
            if " ".join(product.title.casefold().split()) == "busy bar"
        ]
        if len(products) != 1:
            raise ValueError("Shopify Stats must contain exactly one BUSY Bar product")
        return products[0].qty


class SalesObservation(BaseModel):
    """Represent one timestamped cumulative BUSY Bar sales observation."""

    observed_at: datetime
    bars_sold: int = Field(ge=0)
    source_updated_at: datetime
