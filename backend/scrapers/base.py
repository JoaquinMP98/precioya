from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScrapedProduct:
    name: str
    price: float
    url: str
    supermarket: str
    price_per_unit: str | None = None
    image_url: str | None = None
    brand: str | None = None
    category: str | None = None


class BaseScraper(ABC):
    supermarket_slug: str = ""

    @abstractmethod
    async def search(self, query: str) -> list[ScrapedProduct]:
        """Search products by keyword. Returns empty list on failure."""
        ...

    @abstractmethod
    async def get_product(self, url: str) -> ScrapedProduct | None:
        """Fetch a single product by URL. Returns None on failure."""
        ...
