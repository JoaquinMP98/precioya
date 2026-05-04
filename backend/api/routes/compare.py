import logging
import re
import unicodedata
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from api.schemas.compare import CompareResponse, MarketResult, SupermarketGroup
from core.nutriscore_cache import get_nutriscore
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


def _normalize(text: str) -> str:
    """Lowercase and strip diacritics so ñ→n, á→a, etc. for boundary matching."""
    nfkd = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _relevance_score(product_name: str, query: str) -> int | None:
    """
    Return a relevance tier (0 = best) or None to exclude the product.

    Exclusion rule: every word in the query must appear as a whole word
    (word-boundary match on normalised text) in the product name.  This removes
    false positives such as "Champán" or "Pantalón" when the query is "pan".

    Tiers:
      0  — normalised name equals normalised query exactly
      1  — name starts with the full query ("pan de molde" for query "pan")
      2  — every query word is present as a whole word somewhere in the name
    """
    name_n = _normalize(product_name)
    query_n = _normalize(query)

    for word in query_n.split():
        if not re.search(rf"\b{re.escape(word)}\b", name_n):
            return None  # query word absent as a standalone word → exclude

    if name_n == query_n:
        return 0
    if re.match(rf"^{re.escape(query_n)}\b", name_n):
        return 1
    return 2


@router.get("/compare", response_model=CompareResponse)
async def compare_products(
    q: Annotated[str, Query(min_length=2, max_length=100, description="Search term")],
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    """
    Return all matching products grouped by supermarket.

    Products are filtered by relevance (query words must appear as whole words
    in the product name) and sorted within each group by relevance tier first,
    then price. Groups are ordered by their cheapest product price.
    `cheapest` is the single lowest-priced result across all markets.
    """
    products, from_cache, warnings = await search_with_cache(q, db)

    # Score every product; exclude those that only match query as a substring.
    scored: list[tuple[int, MarketResult]] = []
    for p in products:
        score = _relevance_score(p.name, q)
        if score is None:
            continue
        scored.append((
            score,
            MarketResult(
                supermarket=p.supermarket,
                product_name=p.name,
                price=p.price,
                price_per_unit=p.price_per_unit,
                url=p.url,
                image_url=p.image_url,
            ),
        ))

    # Group by supermarket.
    buckets: dict[str, list[tuple[int, MarketResult]]] = {}
    for score, result in scored:
        buckets.setdefault(result.supermarket, []).append((score, result))

    # Within each group sort by (relevance_tier, price); sort groups by min price.
    by_supermarket = [
        SupermarketGroup(
            supermarket=slug,
            products=[r for _, r in sorted(items, key=lambda x: (x[0], x[1].price))],
        )
        for slug, items in buckets.items()
    ]
    by_supermarket.sort(key=lambda g: min(r.price for r in g.products))

    # Flag the best price-per-unit within each group for each recognised unit.
    for group in by_supermarket:
        best: dict[str, tuple[float, MarketResult]] = {}
        for result in group.products:
            parsed = _parse_unit_price(result.price_per_unit)
            if parsed is None:
                continue
            value, unit = parsed
            if unit not in best or value < best[unit][0]:
                best[unit] = (value, result)
        for _, winner in best.values():
            winner.best_unit_price = True

    # Enrich top-5 products per group with Nutri-Score (serialised; optional).
    try:
        candidates = [r for g in by_supermarket for r in g.products[:5]]
        for result in candidates:
            grade, nova = await get_nutriscore(result.product_name)
            result.nutriscore = grade
            result.nova_group = nova
        if candidates:
            first = candidates[0]
            logger.info(
                "nutriscore sample — %r: nutriscore=%s nova=%s",
                first.product_name,
                first.nutriscore,
                first.nova_group,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("nutriscore enrichment failed: %s", exc)
        # nutriscore is optional; continue without it

    # Flag best nutriscore within each supermarket group.
    _GRADE_ORDER = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4}
    for group in by_supermarket:
        best_grade: str | None = None
        best_result: MarketResult | None = None
        for result in group.products:
            if result.nutriscore and (
                best_grade is None
                or _GRADE_ORDER[result.nutriscore] < _GRADE_ORDER[best_grade]
            ):
                best_grade = result.nutriscore
                best_result = result
        if best_result:
            best_result.best_nutriscore = True

    # Cheapest is the absolute minimum price across all relevant products.
    cheapest = (
        min((r for g in by_supermarket for r in g.products), key=lambda r: r.price)
        if by_supermarket else None
    )

    return CompareResponse(
        query=q,
        cheapest=cheapest,
        by_supermarket=by_supermarket,
        from_cache=from_cache,
        warnings=warnings,
    )
