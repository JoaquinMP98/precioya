from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.search import SearchResponse, SearchResult
from core.search_service import search_with_cache
from db.database import get_db

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search_products(
    q: Annotated[str, Query(min_length=2, max_length=100, description="Search term")],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Search products across all supermarkets.
    Served from cache (24 h TTL) on repeat queries; scrapes live on first call.
    Always returns 200 — scraper failures appear in `warnings`.
    Results sorted by price ascending.
    """
    products, from_cache, warnings = await search_with_cache(q, db)
    products.sort(key=lambda p: p.price)

    results = [
        SearchResult(
            name=p.name,
            price=p.price,
            supermarket=p.supermarket,
            url=p.url,
            price_per_unit=p.price_per_unit,
            image_url=p.image_url,
            brand=p.brand,
            category=p.category,
        )
        for p in products[:limit]
    ]

    return SearchResponse(
        query=q,
        total=len(results),
        results=results,
        from_cache=from_cache,
        warnings=warnings,
    )
