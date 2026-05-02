import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import Price, Product, SearchCache
from scrapers.base import ScrapedProduct

logger = logging.getLogger(__name__)


def _normalize(query: str) -> str:
    return query.lower().strip()


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _cutoff() -> datetime:
    return _now() - timedelta(hours=settings.cache_ttl_hours)


async def is_query_fresh(db: AsyncSession, query: str) -> bool:
    result = await db.execute(
        select(SearchCache)
        .where(SearchCache.query == _normalize(query))
        .where(SearchCache.cached_at >= _cutoff())
        .limit(1)
    )
    return result.scalars().first() is not None


async def get_cached_results(db: AsyncSession, query: str) -> list[ScrapedProduct]:
    ids_result = await db.execute(
        select(SearchCache.product_id)
        .where(SearchCache.query == _normalize(query))
        .where(SearchCache.cached_at >= _cutoff())
        .distinct()
    )
    product_ids = ids_result.scalars().all()
    if not product_ids:
        return []

    products_result = await db.execute(
        select(Product).where(Product.id.in_(product_ids))
    )
    products = products_result.scalars().all()

    out: list[ScrapedProduct] = []
    for product in products:
        price_result = await db.execute(
            select(Price)
            .where(Price.product_id == product.id)
            .order_by(Price.scraped_at.desc())
            .limit(1)
        )
        price = price_result.scalars().first()
        if price is None:
            continue
        out.append(
            ScrapedProduct(
                name=product.name,
                price=price.price,
                price_per_unit=price.price_per_unit,
                image_url=product.image_url,
                url=product.url,
                supermarket=product.supermarket,
                brand=product.brand,
                category=product.category,
            )
        )

    return out


async def get_stale_results_for_supermarkets(
    db: AsyncSession,
    query: str,
    supermarkets: list[str],
) -> list[ScrapedProduct]:
    """Return the most recent cached results for the given supermarkets, ignoring TTL."""
    ids_result = await db.execute(
        select(SearchCache.product_id)
        .join(Product, Product.id == SearchCache.product_id)
        .where(SearchCache.query == _normalize(query))
        .where(Product.supermarket.in_(supermarkets))
        .distinct()
    )
    product_ids = ids_result.scalars().all()
    if not product_ids:
        return []

    products_result = await db.execute(
        select(Product).where(Product.id.in_(product_ids))
    )
    products = products_result.scalars().all()

    out: list[ScrapedProduct] = []
    for product in products:
        price_result = await db.execute(
            select(Price)
            .where(Price.product_id == product.id)
            .order_by(Price.scraped_at.desc())
            .limit(1)
        )
        price = price_result.scalars().first()
        if price is None:
            continue
        out.append(
            ScrapedProduct(
                name=product.name,
                price=price.price,
                price_per_unit=price.price_per_unit,
                image_url=product.image_url,
                url=product.url,
                supermarket=product.supermarket,
                brand=product.brand,
                category=product.category,
            )
        )
    return out


async def save_results(
    db: AsyncSession,
    query: str,
    products: list[ScrapedProduct],
) -> None:
    norm = _normalize(query)
    now = _now()

    for scraped in products:
        result = await db.execute(select(Product).where(Product.url == scraped.url))
        product = result.scalars().first()

        if product is None:
            product = Product(
                name=scraped.name,
                supermarket=scraped.supermarket,
                url=scraped.url,
                brand=scraped.brand,
                category=scraped.category,
                image_url=scraped.image_url,
            )
            db.add(product)
            await db.flush()
        else:
            product.name = scraped.name
            product.image_url = scraped.image_url

        db.add(Price(
            product_id=product.id,
            price=scraped.price,
            price_per_unit=scraped.price_per_unit,
            scraped_at=now,
        ))
        db.add(SearchCache(
            query=norm,
            product_id=product.id,
            cached_at=now,
        ))

    await db.commit()
    logger.debug("Saved %d products for query %r", len(products), query)
