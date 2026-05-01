from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.compare import CompareResponse, MarketResult
from core.search_service import search_with_cache
from db.database import get_db

router = APIRouter()


@router.get("/compare", response_model=CompareResponse)
async def compare_products(
    q: Annotated[str, Query(min_length=2, max_length=100, description="Search term")],
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    """
    Return the cheapest product per supermarket for a given search term.
    Uses the same cache as /search so a prior search costs nothing extra.
    `cheapest` is the single best deal across all markets.
    """
    products, from_cache, warnings = await search_with_cache(q, db)

    # One entry per supermarket: the cheapest product in that market
    best_by_market: dict[str, MarketResult] = {}
    for p in products:
        if p.supermarket not in best_by_market or p.price < best_by_market[p.supermarket].price:
            best_by_market[p.supermarket] = MarketResult(
                supermarket=p.supermarket,
                product_name=p.name,
                price=p.price,
                price_per_unit=p.price_per_unit,
                url=p.url,
                image_url=p.image_url,
            )

    by_supermarket = sorted(best_by_market.values(), key=lambda r: r.price)
    cheapest = by_supermarket[0] if by_supermarket else None

    return CompareResponse(
        query=q,
        cheapest=cheapest,
        by_supermarket=by_supermarket,
        from_cache=from_cache,
        warnings=warnings,
    )
