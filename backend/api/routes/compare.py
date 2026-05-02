import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.compare import CompareResponse, MarketResult, SupermarketGroup
from core.search_service import search_with_cache
from db.database import get_db

router = APIRouter()

# Matches "0.57 €/L", "1,99 €/kg", "2.58 €/ml", "0.45 €/g" (case-insensitive unit)
_UNIT_PRICE_RE = re.compile(r"(\d+[.,]\d+)\s*€\s*/\s*(L|kg|ml|g)\b", re.IGNORECASE)


def _parse_unit_price(price_per_unit: str | None) -> tuple[float, str] | None:
    """Return (value, normalised_unit) or None if unparseable / unrecognised unit."""
    if not price_per_unit:
        return None
    m = _UNIT_PRICE_RE.search(price_per_unit)
    if not m:
        return None
    return float(m.group(1).replace(",", ".")), m.group(2).lower()


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

    # Within each supermarket group, flag the product with the lowest price per
    # unit for each recognised unit (L, kg, ml, g).
    for group in by_supermarket:
        best: dict[str, tuple[float, MarketResult]] = {}  # unit → (value, result)
        for result in group.products:
            parsed = _parse_unit_price(result.price_per_unit)
            if parsed is None:
                continue
            value, unit = parsed
            if unit not in best or value < best[unit][0]:
                best[unit] = (value, result)
        for _, winner in best.values():
            winner.best_unit_price = True

    cheapest = by_supermarket[0].products[0] if by_supermarket else None

    return CompareResponse(
        query=q,
        cheapest=cheapest,
        by_supermarket=by_supermarket,
        from_cache=from_cache,
        warnings=warnings,
    )
