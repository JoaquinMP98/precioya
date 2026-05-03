import asyncio
import logging
import random
import re

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from scrapers.base import BaseScraper, ScrapedProduct

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.dia.es"
_SEARCH_URL = f"{_BASE_URL}/tienda/buscar"
_GRID_SELECTOR = ".catalog-product-item, [class*='product-item'], [class*='product-card']"
_TIMEOUT = 15_000

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

_EXTRACT_GRID_JS = """
() => {
    const cards = Array.from(
        document.querySelectorAll('.catalog-product-item') ||
        document.querySelectorAll('[class*="product-item"]') ||
        document.querySelectorAll('[class*="product-card"]')
    );
    return cards.map(card => {
        const linkEl = card.querySelector('a[href*="/producto/"]') ||
                       card.querySelector('a[href*="/product/"]') ||
                       card.querySelector('a[href*="/p/"]') ||
                       card.querySelector('a[href]');
        const href = linkEl ? linkEl.getAttribute('href') : '';
        const url = href.startsWith('http') ? href : ('%BASE%' + href);

        const nameEl = card.querySelector('.product-item__name') ||
                       card.querySelector('[class*="product-name"]') ||
                       card.querySelector('[class*="product-title"]') ||
                       card.querySelector('[class*="item-name"]') ||
                       card.querySelector('h2, h3');
        const name = nameEl ? nameEl.textContent.trim() : '';

        const priceEl = card.querySelector('.product-item__price') ||
                        card.querySelector('[class*="product-price"]') ||
                        card.querySelector('[class*="item-price"]') ||
                        card.querySelector('[class*="price-value"]') ||
                        card.querySelector('[class*="price"]');
        const price = priceEl ? priceEl.textContent.trim() : '';

        const unitEl = card.querySelector('[class*="price-per-unit"]') ||
                       card.querySelector('[class*="unit-price"]') ||
                       card.querySelector('[class*="price-unit"]');
        const price_per_unit = unitEl ? unitEl.textContent.trim() : null;

        const imgEl = card.querySelector('img[src*="dia"]') ||
                      card.querySelector('img[loading="lazy"]') ||
                      card.querySelector('img');
        const image_url = imgEl ? (imgEl.src || imgEl.dataset.src || null) : null;

        return { name, url, price, price_per_unit, image_url };
    });
}
""".replace("%BASE%", _BASE_URL)

_EXTRACT_DETAIL_JS = """
() => {
    const nameEl = document.querySelector('h1.product-detail__name') ||
                   document.querySelector('[class*="product-detail"] h1') ||
                   document.querySelector('[class*="product-name"]') ||
                   document.querySelector('h1');
    const name = nameEl ? nameEl.textContent.trim() : '';

    const priceEl = document.querySelector('[class*="product-price"]') ||
                    document.querySelector('[class*="price-value"]') ||
                    document.querySelector('[class*="price"]');
    const price = priceEl ? priceEl.textContent.trim() : '';

    const unitEl = document.querySelector('[class*="price-per-unit"]') ||
                   document.querySelector('[class*="unit-price"]');
    const price_per_unit = unitEl ? unitEl.textContent.trim() : null;

    const imgEl = document.querySelector('.product-detail__image img') ||
                  document.querySelector('[class*="product"] img');
    const image_url = imgEl ? (imgEl.src || null) : null;

    return { name, price, price_per_unit, image_url };
}
"""


def _parse_price(text: str) -> float | None:
    """'1,99\xa0€' → 1.99"""
    clean = re.sub(r"[^\d,.]", "", text).replace(",", ".")
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
    ppu = (raw.get("price_per_unit") or "").strip() or None
    img = (raw.get("image_url") or "").strip() or None

    return ScrapedProduct(
        name=name,
        price=price,
        price_per_unit=ppu,
        image_url=img,
        url=url,
        supermarket="dia",
    )


class DiaScraper(BaseScraper):
    supermarket_slug = "dia"

    def __init__(self, headless: bool = True, timeout: int = _TIMEOUT) -> None:
        self._headless = headless
        self._timeout = timeout

    async def search(self, query: str) -> list[ScrapedProduct]:
        await asyncio.sleep(random.uniform(0.8, 1.5))
        try:
            return await self._do_search(query)
        except Exception as exc:
            logger.warning("DIA search failed for %r: %s", query, exc)
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
                    f"{_SEARCH_URL}/?q={query}",
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
                logger.warning("DIA search timed out for %r", query)
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
            logger.warning("DIA get_product failed for %s: %s", url, exc)
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
                    "[class*='product-price'], [class*='price-value'], [class*='price']",
                    state="attached",
                    timeout=self._timeout,
                )
                await asyncio.sleep(0.5)
                raw: dict = await page.evaluate(_EXTRACT_DETAIL_JS)
            except PlaywrightTimeout:
                logger.warning("DIA get_product timed out for %s", url)
                return None
            finally:
                await context.close()
                await browser.close()

        return _build_product(raw, url_fallback=url)
