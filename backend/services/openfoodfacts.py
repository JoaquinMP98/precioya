import logging

import httpx

logger = logging.getLogger(__name__)

_BARCODE_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}"
_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
_FIELDS = "product_name,nutrition_grades,nova_groups,brands"
_TIMEOUT = 8.0
_USER_AGENT = "PrecioYa/1.0 (https://github.com/JoaquinMP98/precioya - joaquinmartinezpaz@gmail.com)"
_HEADERS = {"User-Agent": _USER_AGENT}

_VALID_GRADES = {"a", "b", "c", "d", "e"}


def _grade(raw: str | None) -> str | None:
    if not raw:
        return None
    g = raw.strip().lower()
    return g if g in _VALID_GRADES else None


def _nova(raw) -> int | None:
    try:
        n = int(raw)
        return n if 1 <= n <= 4 else None
    except (TypeError, ValueError):
        return None


async def _get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response | None:
    """GET with one exponential-backoff retry on 503."""
    resp = await client.get(url, **kwargs)
    if resp.status_code == 503:
        logger.warning("OFF rate-limited (503) — retrying in 3 s")
        import asyncio  # local import to keep top-level clean
        await asyncio.sleep(3)
        resp = await client.get(url, **kwargs)
        if resp.status_code == 503:
            logger.warning("OFF still 503 after retry — skipping")
            return None
    return resp


async def get_nutriscore_by_barcode(barcode: str) -> tuple[str | None, int | None]:
    """Return (nutrition_grade, nova_group) for a barcode, or (None, None)."""
    url = _BARCODE_URL.format(barcode=barcode)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await _get(client, url, params={"fields": _FIELDS})
            if resp is None:
                return None, None
            resp.raise_for_status()
            data = resp.json()
        product = data.get("product") or {}
        return _grade(product.get("nutrition_grades")), _nova(product.get("nova_groups"))
    except Exception as exc:  # noqa: BLE001
        logger.debug("OFF barcode lookup failed for %s: %s", barcode, exc)
        return None, None


async def get_nutriscore_by_name(
    name: str,
    brand: str | None = None,
) -> tuple[str | None, int | None]:
    """
    Search Open Food Facts by product name and optional brand.
    Returns (nutrition_grade, nova_group) for the best matching hit, or (None, None).
    """
    terms = f"{name} {brand}".strip() if brand else name
    params = {
        "search_terms": terms,
        "json": "1",
        "fields": _FIELDS,
        "page_size": "5",
        "lc": "es",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
            resp = await _get(client, _SEARCH_URL, params=params)
            if resp is None:
                return None, None
            resp.raise_for_status()
            data = resp.json()
        hits = data.get("products") or []
        # Pick the first hit that has a nutrition grade.
        for hit in hits:
            grade = _grade(hit.get("nutrition_grades"))
            if grade:
                return grade, _nova(hit.get("nova_groups"))
        return None, None
    except Exception as exc:  # noqa: BLE001
        logger.debug("OFF name search failed for %r: %s", name, exc)
        return None, None
