import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import get_cached_results, is_query_fresh, save_results
from core.config import settings
from scrapers.alcampo.scraper import AlcampoScraper
from scrapers.base import BaseScraper, ScrapedProduct
from scrapers.lidl.scraper import LidlScraper
from scrapers.mercadona.scraper import MercadonaScraper

logger = logging.getLogger(__name__)

_PW_TIMEOUT_MS = int(settings.scraper_timeout * 1000)

SCRAPERS: list[BaseScraper] = [
    MercadonaScraper(timeout=settings.scraper_timeout),
    LidlScraper(headless=settings.playwright_headless, timeout=_PW_TIMEOUT_MS),
    AlcampoScraper(headless=settings.playwright_headless, timeout=_PW_TIMEOUT_MS),
]


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
    """
    if await is_query_fresh(db, query):
        logger.debug("Cache hit for %r", query)
        cached = await get_cached_results(db, query)
        return cached, True, []

    logger.debug("Cache miss for %r — fanning out to scrapers", query)
    warnings: list[str] = []
    batches = await asyncio.gather(*[_run_scraper(s, query, warnings) for s in SCRAPERS])
    products = [p for batch in batches for p in batch]

    if products:
        await save_results(db, query, products)

    return products, False, warnings
