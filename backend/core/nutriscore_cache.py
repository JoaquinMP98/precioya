"""DB-backed cache for Nutri-Score lookups (keyed by normalised product name)."""

import asyncio
import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import NutriscoreCache
from services.openfoodfacts import get_nutriscore_by_name

logger = logging.getLogger(__name__)

_TTL = timedelta(days=30)
_SEMAPHORE = asyncio.Semaphore(3)  # cap concurrent OFF API calls


def _name_key(product_name: str) -> str:
    """Normalised lowercase key: strip accents + non-alphanumerics, collapse spaces."""
    nfkd = unicodedata.normalize("NFD", product_name.lower())
    ascii_only = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", ascii_only)).strip()


async def _fetch_from_db(
    db: AsyncSession, key: str
) -> NutriscoreCache | None:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - _TTL
    result = await db.execute(
        select(NutriscoreCache).where(
            NutriscoreCache.product_name_key == key,
            NutriscoreCache.cached_at >= cutoff,
        )
    )
    return result.scalar_one_or_none()


async def _upsert(
    db: AsyncSession, key: str, nutriscore: str | None, nova_group: int | None
) -> None:
    stmt = (
        insert(NutriscoreCache)
        .values(
            product_name_key=key,
            nutriscore=nutriscore,
            nova_group=nova_group,
            cached_at=datetime.now(UTC).replace(tzinfo=None),
        )
        .on_conflict_do_update(
            index_elements=["product_name_key"],
            set_={"nutriscore": nutriscore, "nova_group": nova_group, "cached_at": datetime.now(UTC).replace(tzinfo=None)},
        )
    )
    await db.execute(stmt)
    await db.commit()


async def get_nutriscore(
    db: AsyncSession, product_name: str
) -> tuple[str | None, int | None]:
    """Return (nutriscore, nova_group) from cache or OFF API."""
    key = _name_key(product_name)
    if not key:
        return None, None

    cached = await _fetch_from_db(db, key)
    if cached is not None:
        return cached.nutriscore, cached.nova_group

    async with _SEMAPHORE:
        grade, nova = await get_nutriscore_by_name(product_name)

    await _upsert(db, key, grade, nova)
    return grade, nova
