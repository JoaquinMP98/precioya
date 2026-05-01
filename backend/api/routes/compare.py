from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.compare import CompareResponse, MarketResult, SupermarketGroup
from core.search_service import search_with_cache
from db.database import get_db

router = APIRouter()


@router.get("/compare", response_model=CompareResponse)
async def compare_products(
    q: Annotated[str, Query(min_length=2, max_length=100, description="Search term")],
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    """
    Return all matching products grouped by supermarket, sorted by price within
    each group. Groups are ordered by their cheapest product. `cheapest` is the
    single best deal across all markets.
    """
    products, from_cache, warnings = await search_with_cache(q, db)

    # Collect all products into per-supermarket buckets
    buckets: dict[str, list[MarketResult]] = {}
    for p in products:
        result = MarketResult(
            supermarket=p.supermarket,
            product_name=p.name,
            price=p.price,
            price_per_unit=p.price_per_unit,
            url=p.url,
            image_url=p.image_url,
        )
        buckets.setdefault(p.supermarket, []).append(result)

    # Sort products within each group by price, then sort groups by their cheapest
    by_supermarket = [
        SupermarketGroup(
            supermarket=slug,
            products=sorted(items, key=lambda r: r.price),
        )
        for slug, items in buckets.items()
    ]
    by_supermarket.sort(key=lambda g: g.products[0].price)

    cheapest = by_supermarket[0].products[0] if by_supermarket else None

    return CompareResponse(
        query=q,
        cheapest=cheapest,
        by_supermarket=by_supermarket,
        from_cache=from_cache,
        warnings=warnings,
    )
