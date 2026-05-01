import asyncio
import logging
import random
import re

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.lidl.es"
_SEARCH_URL = f"{_BASE_URL}/q/search"  # changed from /p/search (confirmed May 2025)
_GRID_SELECTOR = ".product-grid-box"
_TIMEOUT = 15_000  # 15 s — heavier SPA

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
]

# Extracts all product data from the search results grid in one JS round-trip.
_EXTRACT_GRID_JS = """
() => Array.from(document.querySelectorAll('.product-grid-box')).map(box => {
    const titleEl = (
        box.querySelector('.product-grid-box__title') ||
        box.querySelector('[class*="title"]') ||
        box.querySelector('[class*="description"]')
    );
    const name = titleEl ? titleEl.textContent.trim() : '';

    const linkEl = box.querySelector('a[href]');
    const href = linkEl ? linkEl.getAttribute('href').split('#')[0] : '';
    const url = href.startsWith('http') ? href : '%BASE%' + href;

    const priceEl = (
        box.querySelector('.ods-price__value') ||
        box.querySelector('.m-price__price') ||
        box.querySelector('[class*="price__value"]') ||
        box.querySelector('[class*="price__price"]')
    );
    const price = priceEl ? priceEl.textContent.trim() : '';

    const unitEl = (
        box.querySelector('.ods-price__base-price') ||
        box.querySelector('.m-price__unit-price') ||
        box.querySelector('[class*="base-price"]') ||
        box.querySelector('[class*="unit-price"]')
    );
    const price_per_unit = unitEl ? unitEl.textContent.trim() : null;

    const imgEl = box.querySelector('img');
    const image_url = imgEl ? (imgEl.src || imgEl.dataset.src || '') : null;

    return { name, url, price, price_per_unit, image_url };
})
""".replace("%BASE%", _BASE_URL)

_EXTRACT_DETAIL_JS = """
() => {
    const nameEl = (
        document.querySelector('.product-detail__name') ||
        document.querySelector('[class*="product-title"]') ||
        document.querySelector('h1')
    );
    const name = nameEl ? nameEl.textContent.trim() : '';

    const priceEl = (
        document.querySelector('.ods-price__value') ||
        document.querySelector('.m-price__price') ||
        document.querySelector('[class*="price__value"]') ||
        document.querySelector('[class*="price__price"]')
    );
    const price = priceEl ? priceEl.textContent.trim() : '';

    const unitEl = (
        document.querySelector('.ods-price__base-price') ||
        document.querySelector('.m-price__unit-price') ||
        document.querySelector('[class*="base-price"]') ||
        document.querySelector('[class*="unit-price"]')
    );
    const price_per_unit = unitEl ? unitEl.textContent.trim() : null;

    const imgEl = (
        document.querySelector('.product-detail__image img') ||
        document.querySelector('[class*="product"] img')
    );
    const image_url = imgEl ? (imgEl.src || imgEl.dataset.src || '') : null;

    return { name, price, price_per_unit, image_url };
}
"""


def _parse_price(text: str) -> float | None:
    """'1,99\xa0€' → 1.99"""
    clean = re.sub(r"[^\d,.]", "", text).replace(",", ".")
    # Handle edge cases like "1.234.56" — keep only last dot segment
    parts = clean.split(".")
    if len(parts) > 2:
        clean = "".join(parts[:-1]).replace(".", "") + "." + parts[-1]
    try:
        return round(float(clean), 2)
    except ValueError:
        return None


def _build_product(raw: dict, url_fallback: str = "") -> ScrapedProduct | None:
    name = (raw.get("name") or "").strip()
    price = _parse_price(raw.get("price") or "")
    if not name or price is None:
        return None

    url = (raw.get("url") or url_fallback).strip()
    ppu_raw = (raw.get("price_per_unit") or "").strip() or None
    img = (raw.get("image_url") or "").strip() or None

    return ScrapedProduct(
        name=name,
        price=price,
        price_per_unit=ppu_raw,
        image_url=img,
        url=url,
        supermarket="lidl",
    )


class LidlScraper(BaseScraper):
    supermarket_slug = "lidl"

    def __init__(self, headless: bool = True, timeout: int = _TIMEOUT) -> None:
        self._headless = headless
        self._timeout = timeout

    async def search(self, query: str) -> list[ScrapedProduct]:
        await asyncio.sleep(random.uniform(0.8, 1.5))
        try:
            return await self._do_search(query)
        except Exception as exc:
            logger.warning("Lidl search failed for %r: %s", query, exc)
            return []

    async def _do_search(self, query: str) -> list[ScrapedProduct]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            context = await browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                locale="es-ES",
                extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
            )
            page = await context.new_page()
            try:
                await page.goto(
                    f"{_SEARCH_URL}?q={query}",
                    wait_until="domcontentloaded",
                    timeout=self._timeout,
                )
                await page.wait_for_selector(
                    _GRID_SELECTOR,
                    state="attached",
                    timeout=self._timeout,
                )
                # Let lazy images settle
                await asyncio.sleep(1.0)
                raw_items: list[dict] = await page.evaluate(_EXTRACT_GRID_JS)
            except PlaywrightTimeout:
                logger.warning("Lidl search timed out for %r", query)
                return []
            finally:
                await context.close()
                await browser.close()

        results: list[ScrapedProduct] = []
        for raw in raw_items:
            product = _build_product(raw)
            if product:
                results.append(product)
        return results

    async def get_product(self, url: str) -> ScrapedProduct | None:
        await asyncio.sleep(random.uniform(0.5, 1.0))
        try:
            return await self._do_get_product(url)
        except Exception as exc:
            logger.warning("Lidl get_product failed for %s: %s", url, exc)
            return None

    async def _do_get_product(self, url: str) -> ScrapedProduct | None:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            context = await browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                locale="es-ES",
                extra_http_headers={"Accept-Language": "es-ES,es;q=0.9"},
            )
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self._timeout)
                await page.wait_for_selector(
                    ".ods-price__value, .m-price__price, [class*='price__value']",
                    state="attached",
                    timeout=self._timeout,
                )
                await asyncio.sleep(0.5)
                raw: dict = await page.evaluate(_EXTRACT_DETAIL_JS)
            except PlaywrightTimeout:
                logger.warning("Lidl get_product timed out for %s", url)
                return None
            finally:
                await context.close()
                await browser.close()

        return _build_product(raw, url_fallback=url)
