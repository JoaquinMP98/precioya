import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import get_cached_results, get_stale_results_for_supermarkets, is_query_fresh, save_results
from core.config import settings
from scrapers.alcampo.scraper import AlcampoScraper
from scrapers.aldi.scraper import AldiScraper
from scrapers.base import BaseScraper, ScrapedProduct
from scrapers.lidl.scraper import LidlScraper
from scrapers.mercadona.scraper import MercadonaScraper

logger = logging.getLogger(__name__)

_PW_TIMEOUT_MS = int(settings.scraper_timeout * 1000)

# Mercadona and Aldi use direct APIs (no Playwright) — always active.
SCRAPERS: list[BaseScraper] = [
    MercadonaScraper(timeout=settings.scraper_timeout),
    AldiScraper(timeout=settings.scraper_timeout),
]

if settings.playwright_enabled:
    SCRAPERS += [
        LidlScraper(headless=settings.playwright_headless, timeout=_PW_TIMEOUT_MS),
        AlcampoScraper(headless=settings.playwright_headless, timeout=_PW_TIMEOUT_MS),
    ]
    # Carrefour (Cloudflare Bot Management) and DIA (Akamai) block headless
    # browsers from non-residential IPs. Scrapers are kept in scrapers/ for
    # future use with a proxy service but are not registered here.
else:
    logger.info("Playwright disabled (PLAYWRIGHT_ENABLED=false) — running Mercadona + Aldi only")


async def _run_scraper(
    scraper: BaseScraper,
    query: str,
    warnings: list[str],
) -> list[ScrapedProduct]:
    # Playwright scrapers (Lidl, Alcampo) need browser launch + navigation on top
    # of the configured timeout, so give them scraper_timeout + 10 s of headroom.
    outer_timeout = settings.scraper_timeout + 10.0
    try:
        return await asyncio.wait_for(
            scraper.search(query),
            timeout=outer_timeout,
        )
    except asyncio.TimeoutError:
        msg = f"{scraper.supermarket_slug}: timed out after {outer_timeout}s"
        logger.warning(msg)
        warnings.append(msg)
        return []
    except Exception as exc:  # noqa: BLE001
        msg = f"{scraper.supermarket_slug}: unexpected error — {exc}"
        logger.exception(msg)
        warnings.append(msg)
        return []


async def search_with_cache(
    query: str,
    db: AsyncSession,
) -> tuple[list[ScrapedProduct], bool, list[str]]:
    """
    Return (products, from_cache, warnings).
    Serves from DB cache when the query was scraped within TTL; fans out to
    scrapers otherwise and persists the fresh results.
    When Playwright is disabled, supplements missing supermarkets with their
    most recently stored results regardless of TTL.
    """
    warnings: list[str] = []

    if await is_query_fresh(db, query):
        logger.debug("Cache hit for %r", query)
        products = await get_cached_results(db, query)
        from_cache = True
    else:
        logger.debug("Cache miss for %r — fanning out to scrapers", query)
        batches = await asyncio.gather(*[_run_scraper(s, query, warnings) for s in SCRAPERS])
        products = [p for batch in batches for p in batch]
        if products:
            await save_results(db, query, products)
        from_cache = False

    if not settings.playwright_enabled:
        covered = {p.supermarket for p in products}
        missing = [s for s in ("lidl", "alcampo") if s not in covered]
        if missing:
            stale = await get_stale_results_for_supermarkets(db, query, missing)
            if stale:
                products = products + stale
                stale_supermarkets = sorted({p.supermarket for p in stale})
                names = " y ".join(s.capitalize() for s in stale_supermarkets)
                warnings.append(f"{names}: precios anteriores (Playwright desactivado)")

    return products, from_cache, warnings
