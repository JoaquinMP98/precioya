from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    name: str
    price: float
    supermarket: str
    url: str
    price_per_unit: str | None = None
    image_url: str | None = None
    brand: str | None = None
    category: str | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]
    from_cache: bool = False
    warnings: list[str] = Field(default_factory=list)
