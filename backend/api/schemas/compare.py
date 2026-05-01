from pydantic import BaseModel, Field


class MarketResult(BaseModel):
    supermarket: str
    product_name: str
    price: float
    price_per_unit: str | None = None
    url: str
    image_url: str | None = None


class SupermarketGroup(BaseModel):
    supermarket: str
    products: list[MarketResult]


class CompareResponse(BaseModel):
    query: str
    cheapest: MarketResult | None
    by_supermarket: list[SupermarketGroup]
    from_cache: bool = False
    warnings: list[str] = Field(default_factory=list)
