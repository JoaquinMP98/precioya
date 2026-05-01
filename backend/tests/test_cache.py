from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.cache import get_cached_results, is_query_fresh, save_results
from db.models import Base, Price, Product, SearchCache
from scrapers.base import ScrapedProduct

# ---- fixtures ----

@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def make_scraped(name: str = "Leche 1L", price: float = 0.65) -> ScrapedProduct:
    return ScrapedProduct(
        name=name,
        price=price,
        url=f"https://tienda.mercadona.es/product/{name.replace(' ', '-')}",
        supermarket="mercadona",
        price_per_unit=f"{price} €/L",
        image_url="https://example.com/img.jpg",
    )


# ---- is_query_fresh ----

@pytest.mark.asyncio
async def test_fresh_returns_false_when_no_cache(db):
    assert await is_query_fresh(db, "leche") is False


@pytest.mark.asyncio
async def test_fresh_returns_true_after_save(db):
    await save_results(db, "leche", [make_scraped()])
    assert await is_query_fresh(db, "leche") is True


@pytest.mark.asyncio
async def test_fresh_normalises_query(db):
    await save_results(db, "leche", [make_scraped()])
    assert await is_query_fresh(db, "  LECHE  ") is True


@pytest.mark.asyncio
async def test_fresh_returns_false_when_expired(db):
    await save_results(db, "leche", [make_scraped()])

    # Back-date the cache entry beyond TTL
    from sqlalchemy import update
    await db.execute(
        update(SearchCache).values(cached_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25))
    )
    await db.commit()

    assert await is_query_fresh(db, "leche") is False


# ---- save_results ----

@pytest.mark.asyncio
async def test_save_creates_product_and_price(db):
    scraped = make_scraped("Leche entera 1L", 0.65)
    await save_results(db, "leche", [scraped])

    from sqlalchemy import select
    products = (await db.execute(select(Product))).scalars().all()
    prices = (await db.execute(select(Price))).scalars().all()

    assert len(products) == 1
    assert products[0].name == "Leche entera 1L"
    assert products[0].supermarket == "mercadona"
    assert len(prices) == 1
    assert prices[0].price == 0.65


@pytest.mark.asyncio
async def test_save_upserts_existing_product(db):
    url = "https://tienda.mercadona.es/product/Leche-1L"
    p1 = ScrapedProduct(name="Leche 1L", price=0.65, url=url, supermarket="mercadona")
    p2 = ScrapedProduct(name="Leche 1L (oferta)", price=0.55, url=url, supermarket="mercadona")

    await save_results(db, "leche", [p1])
    await save_results(db, "leche", [p2])

    from sqlalchemy import select
    products = (await db.execute(select(Product))).scalars().all()
    prices = (await db.execute(select(Price))).scalars().all()

    # Only one product row (same URL), but two price history rows
    assert len(products) == 1
    assert products[0].name == "Leche 1L (oferta)"
    assert len(prices) == 2


@pytest.mark.asyncio
async def test_save_empty_list_is_noop(db):
    await save_results(db, "leche", [])

    from sqlalchemy import select
    assert (await db.execute(select(Product))).scalars().all() == []


# ---- get_cached_results ----

@pytest.mark.asyncio
async def test_get_cached_returns_saved_products(db):
    scraped = [make_scraped("Leche entera 1L", 0.65), make_scraped("Leche semidesnatada 1L", 0.62)]
    await save_results(db, "leche", scraped)

    results = await get_cached_results(db, "leche")
    assert len(results) == 2
    names = {r.name for r in results}
    assert "Leche entera 1L" in names
    assert "Leche semidesnatada 1L" in names


@pytest.mark.asyncio
async def test_get_cached_returns_latest_price(db):
    url = "https://tienda.mercadona.es/product/Leche-1L"
    await save_results(db, "leche", [ScrapedProduct(name="Leche 1L", price=0.70, url=url, supermarket="mercadona")])
    await save_results(db, "leche", [ScrapedProduct(name="Leche 1L", price=0.65, url=url, supermarket="mercadona")])

    results = await get_cached_results(db, "leche")
    assert results[0].price == 0.65


@pytest.mark.asyncio
async def test_get_cached_returns_empty_when_expired(db):
    await save_results(db, "leche", [make_scraped()])

    from sqlalchemy import update
    await db.execute(
        update(SearchCache).values(cached_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=25))
    )
    await db.commit()

    results = await get_cached_results(db, "leche")
    assert results == []
