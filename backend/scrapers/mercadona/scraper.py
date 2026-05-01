import asyncio
import logging
import random

import httpx

from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)

# Mercadona migrated from /api/search/ to Algolia (confirmed May 2025).
_ALGOLIA_APP_ID = "7UZJKL1DJ0"
_ALGOLIA_API_KEY = "9d8f2e39e90df472b4f2e559a116fe17"
_ALGOLIA_INDEX = "products_prod"
_ALGOLIA_SEARCH_URL = (
    f"https://{_ALGOLIA_APP_ID.lower()}-dsn.algolia.net"
    f"/1/indexes/{_ALGOLIA_INDEX}/query"
)
_ALGOLIA_OBJECT_URL = (
    f"https://{_ALGOLIA_APP_ID.lower()}-dsn.algolia.net"
    f"/1/indexes/{_ALGOLIA_INDEX}"
)
_ALGOLIA_HEADERS = {
    "X-Algolia-Application-Id": _ALGOLIA_APP_ID,
    "X-Algolia-API-Key": _ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}


def _parse_product(raw: dict) -> ScrapedProduct | None:
    try:
        display = raw.get("display_name") or raw.get("slug", "")
        price_info = raw.get("price_instructions", {})
        unit_price = price_info.get("unit_price")
        if unit_price is None:
            return None

        reference_price = price_info.get("reference_price")
        reference_format = price_info.get("reference_format", "")
        price_per_unit = (
            f"{reference_price} €/{reference_format}" if reference_price else None
        )

        # Algolia response uses `thumbnail` (str); old REST API used `photos[0].regular`
        thumbnail = raw.get("thumbnail")
        photos = raw.get("photos", [])
        image_url = thumbnail or (photos[0].get("regular") if photos else None)

        product_id = raw.get("objectID") or raw.get("id")
        url = f"https://tienda.mercadona.es/product/{product_id}" if product_id else ""

        return ScrapedProduct(
            name=display,
            price=float(unit_price),
            price_per_unit=price_per_unit,
            image_url=image_url,
            url=url,
            supermarket="mercadona",
            brand=raw.get("brand"),
            category=raw.get("categories", [{}])[0].get("name") if raw.get("categories") else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("Could not parse Mercadona product %s: %s", raw.get("objectID") or raw.get("id"), exc)
        return None


class MercadonaScraper(BaseScraper):
    supermarket_slug = "mercadona"

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def search(self, query: str) -> list[ScrapedProduct]:
        await asyncio.sleep(random.uniform(0.5, 1.5))
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    _ALGOLIA_SEARCH_URL,
                    headers=_ALGOLIA_HEADERS,
                    json={"query": query, "hitsPerPage": 20},
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Mercadona search failed for %r: %s", query, exc)
            return []

        hits: list[dict] = resp.json().get("hits", [])
        parsed = [_parse_product(h) for h in hits]
        return [p for p in parsed if p is not None]

    async def get_product(self, url: str) -> ScrapedProduct | None:
        object_id = url.rstrip("/").split("/")[-1]
        if not object_id.isdigit():
            logger.warning("Cannot derive product ID from URL: %s", url)
            return None

        await asyncio.sleep(random.uniform(0.3, 0.8))
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{_ALGOLIA_OBJECT_URL}/{object_id}",
                    headers=_ALGOLIA_HEADERS,
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Mercadona get_product failed for %s: %s", url, exc)
            return None

        return _parse_product(resp.json())
