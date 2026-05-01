import asyncio
import logging
import random
import re

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)

# Alcampo moved online shop to compraonline.alcampo.es (confirmed May 2025).
_BASE_URL = "https://www.compraonline.alcampo.es"
_SEARCH_URL = f"{_BASE_URL}/search"
_TIMEOUT = 15_000
_GRID_SELECTOR = ".product-card-container"

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
]

_EXTRACT_GRID_JS = """
() => Array.from(document.querySelectorAll('.product-card-container')).map(card => {
    const linkEl = card.querySelector('a[data-test="fop-product-link"]') ||
                   card.querySelector('a[href*="/products/"]');
    const href = linkEl ? linkEl.getAttribute('href') : '';
    const nameEl = linkEl ? (linkEl.querySelector('.salt-vc') || linkEl) : null;
    const name = nameEl ? nameEl.textContent.trim() : '';

    const imgEl = card.querySelector('img[data-test="lazy-load-image"]') ||
                  card.querySelector('img');
    const image_url = imgEl ? imgEl.src || imgEl.dataset.src || null : null;

    const priceEl = card.querySelector('[data-test="fop-price"]') ||
                    card.querySelector('[class*="price"]');
    const price = priceEl ? priceEl.textContent.trim() : '';

    const unitEl = card.querySelector('[data-test="fop-unit-price"]') ||
                   card.querySelector('[class*="unit-price"]') ||
                   card.querySelector('[class*="unitPrice"]');
    const price_per_unit = unitEl ? unitEl.textContent.trim() : null;

    const url = href ? ('%BASE%' + href) : '';
    return { name, url, price, price_per_unit, image_url };
})
""".replace("%BASE%", _BASE_URL)

_EXTRACT_DETAIL_JS = """
() => {
    const nameEl = document.querySelector('h1') ||
                   document.querySelector('[class*="product-name"]') ||
                   document.querySelector('[class*="productName"]');
    const name = nameEl ? nameEl.textContent.trim() : '';

    const priceEl = document.querySelector('[data-test="bop-price"]') ||
                    document.querySelector('[data-test="fop-price"]') ||
                    document.querySelector('[class*="price"]');
    const price = priceEl ? priceEl.textContent.trim() : '';

    const unitEl = document.querySelector('[data-test="bop-unit-price"]') ||
                   document.querySelector('[class*="unit-price"]');
    const price_per_unit = unitEl ? unitEl.textContent.trim() : null;

    const imgEl = document.querySelector('img[data-test="lazy-load-image"]') ||
                  document.querySelector('[class*="product"] img');
    const image_url = imgEl ? imgEl.src || null : null;

    return { name, price, price_per_unit, image_url };
}
"""


def _parse_price(text: str) -> float | None:
    clean = re.sub(r"[^\d,.]", "", text).replace(",", ".")
    parts = clean.split(".")
    if len(parts) > 2:
        clean = "".join(parts[:-1]) + "." + parts[-1]
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
    ppu = (raw.get("price_per_unit") or "").strip() or None
    img = (raw.get("image_url") or "").strip() or None

    return ScrapedProduct(
        name=name,
        price=price,
        price_per_unit=ppu,
        image_url=img,
        url=url,
        supermarket="alcampo",
    )


class AlcampoScraper(BaseScraper):
    supermarket_slug = "alcampo"

    def __init__(self, headless: bool = True, timeout: int = _TIMEOUT) -> None:
        self._headless = headless
        self._timeout = timeout

    async def search(self, query: str) -> list[ScrapedProduct]:
        await asyncio.sleep(random.uniform(0.8, 1.5))
        try:
            return await self._do_search(query)
        except Exception as exc:
            logger.warning("Alcampo search failed for %r: %s", query, exc)
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
                await asyncio.sleep(1.0)
                raw_items: list[dict] = await page.evaluate(_EXTRACT_GRID_JS)
            except PlaywrightTimeout:
                logger.warning("Alcampo search timed out for %r", query)
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
            logger.warning("Alcampo get_product failed for %s: %s", url, exc)
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
                    "[data-test='bop-price'], [data-test='fop-price'], [class*='price']",
                    state="attached",
                    timeout=self._timeout,
                )
                await asyncio.sleep(0.5)
                raw: dict = await page.evaluate(_EXTRACT_DETAIL_JS)
            except PlaywrightTimeout:
                logger.warning("Alcampo get_product timed out for %s", url)
                return None
            finally:
                await context.close()
                await browser.close()

        return _build_product(raw, url_fallback=url)
