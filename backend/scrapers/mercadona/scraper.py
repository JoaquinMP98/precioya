import asyncio
import logging
import random
import re

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
# Request only the fields we actually need (categories is NOT in default attributesToRetrieve)
_ALGOLIA_ATTRIBUTES = [
    "display_name", "price_instructions", "thumbnail", "photos",
    "objectID", "id", "brand", "categories", "packaging",
]

_REST_BASE = "https://tienda.mercadona.es"
_REST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Algolia's thumbnail field still has the old date-path imgix format (e.g.
# /20180424/15/10915/...) which returns 404. The REST categories API uses the
# new hash-path format (/images/{md5}.jpg) which works.
_STALE_IMGIX_RE = re.compile(r"/\d{8}/")

# Process-lifetime cache: populated on first search, valid for the process lifetime.
# Maps sub-category name → REST category id.  e.g. "Leche y bebidas vegetales" → 72
_rest_category_ids: dict[str, int] = {}
# Maps REST category id → {display_name: thumbnail_url}
_rest_category_thumbnails: dict[int, dict[str, str]] = {}


def _is_stale(url: str | None) -> bool:
    return bool(url and _STALE_IMGIX_RE.search(url))


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

        thumbnail = raw.get("thumbnail")
        photos = raw.get("photos", [])
        image_url = thumbnail or (photos[0].get("regular") if photos else None)
        # Null out the stale date-path URLs immediately so we don't emit dead links.
        if _is_stale(image_url):
            image_url = None

        product_id = raw.get("objectID") or raw.get("id")
        url = f"https://tienda.mercadona.es/product/{product_id}" if product_id else ""

        cats = raw.get("categories", {})
        category = (
            cats.get("category_level_0", [None])[0]
            if isinstance(cats, dict)
            else None
        )

        return ScrapedProduct(
            name=display,
            price=float(unit_price),
            price_per_unit=price_per_unit,
            image_url=image_url,
            url=url,
            supermarket="mercadona",
            brand=raw.get("brand"),
            category=category,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.debug(
            "Could not parse Mercadona product %s: %s",
            raw.get("objectID") or raw.get("id"),
            exc,
        )
        return None


async def _ensure_category_ids(client: httpx.AsyncClient) -> None:
    """Populate _rest_category_ids from the Mercadona REST categories list (once)."""
    global _rest_category_ids
    if _rest_category_ids:
        return
    try:
        resp = await client.get(
            f"{_REST_BASE}/api/categories/?lang=es", headers=_REST_HEADERS
        )
        resp.raise_for_status()
        for main_cat in resp.json().get("results", []):
            for sub_cat in main_cat.get("categories", []):
                _rest_category_ids[sub_cat["name"]] = sub_cat["id"]
        logger.debug("Mercadona category index built: %d entries", len(_rest_category_ids))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to build Mercadona category index: %s", exc)


async def _fetch_category_thumbnails(
    client: httpx.AsyncClient, cat_id: int
) -> dict[str, str]:
    """Return display_name → thumbnail_url for a REST category (cached per process)."""
    if cat_id in _rest_category_thumbnails:
        return _rest_category_thumbnails[cat_id]

    name_map: dict[str, str] = {}
    try:
        resp = await client.get(
            f"{_REST_BASE}/api/categories/{cat_id}/?lang=es", headers=_REST_HEADERS
        )
        resp.raise_for_status()
        for sub_cat in resp.json().get("categories", []):
            for product in sub_cat.get("products", []):
                thumb = product.get("thumbnail", "")
                if "images/" in thumb:  # only accept new-format working URLs
                    name = product.get("display_name", "")
                    if name and name not in name_map:
                        name_map[name] = thumb
        logger.debug("Fetched %d thumbnails for REST category %d", len(name_map), cat_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch thumbnails for REST category %d: %s", cat_id, exc)

    _rest_category_thumbnails[cat_id] = name_map
    return name_map


async def _enrich_thumbnails(
    client: httpx.AsyncClient,
    products: list[ScrapedProduct],
    hits: list[dict],
) -> None:
    """
    For products whose image_url was nulled (stale Algolia URL), look up a
    working thumbnail from the Mercadona REST categories API by display_name.
    products and hits must be correlated 1:1.
    """
    needs = [i for i, p in enumerate(products) if p.image_url is None]
    if not needs:
        return

    await _ensure_category_ids(client)
    if not _rest_category_ids:
        return

    # Identify which REST sub-categories are needed
    sub_names: set[str] = set()
    for i in needs:
        level_1 = hits[i].get("categories", {}).get("category_level_1", [])
        if level_1:
            # "A > B" → "B"
            sub_names.add(level_1[0].split(" > ")[-1].strip())

    # Fetch needed categories in parallel (only ones not already cached)
    cat_ids_to_fetch = [
        _rest_category_ids[name]
        for name in sub_names
        if name in _rest_category_ids and _rest_category_ids[name] not in _rest_category_thumbnails
    ]
    if cat_ids_to_fetch:
        await asyncio.gather(*[_fetch_category_thumbnails(client, cid) for cid in cat_ids_to_fetch])

    # Enrich each product
    for i in needs:
        level_1 = hits[i].get("categories", {}).get("category_level_1", [])
        if not level_1:
            continue
        sub_name = level_1[0].split(" > ")[-1].strip()
        cat_id = _rest_category_ids.get(sub_name)
        if cat_id is None:
            continue
        thumb = _rest_category_thumbnails.get(cat_id, {}).get(products[i].name)
        if thumb:
            products[i].image_url = thumb


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
                    json={
                        "query": query,
                        "hitsPerPage": 20,
                        "attributesToRetrieve": _ALGOLIA_ATTRIBUTES,
                    },
                )
                resp.raise_for_status()
                hits: list[dict] = resp.json().get("hits", [])

                # Keep correlated (hit, product) pairs to preserve alignment for enrichment.
                pairs = [(h, p) for h in hits if (p := _parse_product(h)) is not None]
                products = [p for _, p in pairs]
                valid_hits = [h for h, _ in pairs]

                await _enrich_thumbnails(client, products, valid_hits)
                return products
        except httpx.HTTPError as exc:
            logger.warning("Mercadona search failed for %r: %s", query, exc)
            return []

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
                    params={"attributesToRetrieve": ",".join(_ALGOLIA_ATTRIBUTES)},
                )
                resp.raise_for_status()
                hit = resp.json()
                product = _parse_product(hit)
                if product is not None:
                    await _enrich_thumbnails(client, [product], [hit])
                return product
        except httpx.HTTPError as exc:
            logger.warning("Mercadona get_product failed for %s: %s", url, exc)
            return None
