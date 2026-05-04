import asyncio
import logging
import random
import re

import httpx

from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)

# Aldi Spain uses Algolia for product search (confirmed May 2026).
_ALGOLIA_APP_ID = "L9KNU74IO7"
_ALGOLIA_API_KEY = "19b0e28f08344395447c7bdeea32da58"
# prod_es_es_es_assortment returns 0 hits; weekly offers index is the live catalog.
_ALGOLIA_INDEX = "prod_es_es_es_offers"
_ALGOLIA_SEARCH_URL = (
    f"https://{_ALGOLIA_APP_ID.lower()}-dsn.algolia.net"
    f"/1/indexes/{_ALGOLIA_INDEX}/query"
)
_ALGOLIA_HEADERS = {
    "X-Algolia-Application-Id": _ALGOLIA_APP_ID,
    "X-Algolia-API-Key": _ALGOLIA_API_KEY,
    "Content-Type": "application/json",
}

_BASE_URL = "https://www.aldi.es"

# "kg = 2,27 €"  →  "2,27 €/kg"
# "100 ml = 2,60 €"  →  "2,60 €/100 ml"
_PPU_RE = re.compile(r"^(.+?)\s*=\s*([\d,.]+)\s*€$")


def _format_price_per_unit(raw: str | None) -> str | None:
    if not raw:
        return None
    m = _PPU_RE.match(raw.strip())
    if not m:
        return None
    unit = m.group(1).strip()
    price = m.group(2).strip()
    return f"{price} €/{unit}"


def _parse_product(hit: dict) -> ScrapedProduct | None:
    try:
        name = (hit.get("productName") or "").strip()
        price = hit.get("salesPrice")
        if not name or price is None:
            return None
        if not hit.get("showPrice", True):
            return None

        url = (hit.get("productUrl") or "").strip()
        if url and not url.startswith("http"):
            url = f"{_BASE_URL}/{url.lstrip('/')}"

        # productPictureRenditions is a srcset string; take first URL
        renditions = hit.get("productPictureRenditions") or ""
        image_url = hit.get("productPicture") or (renditions.split(" ")[0] if renditions else None) or None

        ppu = _format_price_per_unit(hit.get("basePriceFormatted"))

        return ScrapedProduct(
            name=name,
            price=float(price),
            price_per_unit=ppu,
            image_url=image_url or None,
            url=url,
            supermarket="aldi",
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug("Could not parse Aldi hit %s: %s", hit.get("objectID"), exc)
        return None


class AldiScraper(BaseScraper):
    supermarket_slug = "aldi"

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def search(self, query: str) -> list[ScrapedProduct]:
        await asyncio.sleep(random.uniform(0.3, 0.8))
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    _ALGOLIA_SEARCH_URL,
                    headers=_ALGOLIA_HEADERS,
                    json={"query": query, "hitsPerPage": 20},
                )
                resp.raise_for_status()
                hits: list[dict] = resp.json().get("hits", [])
                return [p for h in hits if (p := _parse_product(h)) is not None]
        except httpx.HTTPError as exc:
            logger.warning("Aldi search failed for %r: %s", query, exc)
            return []

    async def get_product(self, url: str) -> ScrapedProduct | None:
        # Aldi offer URLs are time-bound and have no stable single-product API.
        return None
