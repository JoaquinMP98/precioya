"""DB-backed cache for Nutri-Score lookups (keyed by normalised product name)."""

import asyncio
import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from db.database import session_factory
from db.models import NutriscoreCache
from services.openfoodfacts import get_nutriscore_by_name

logger = logging.getLogger(__name__)

_TTL = timedelta(days=30)
# Serial requests: 1 at a time to avoid 503s from Open Food Facts.
_SEMAPHORE = asyncio.Semaphore(1)
_DELAY_S = 2.0


def _name_key(product_name: str) -> str:
    """Normalised lowercase key: strip accents + non-alphanumerics, collapse spaces."""
    nfkd = unicodedata.normalize("NFD", product_name.lower())
    ascii_only = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", ascii_only)).strip()


async def _fetch_from_db(key: str) -> NutriscoreCache | None:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - _TTL
    async with session_factory() as db:
        result = await db.execute(
            select(NutriscoreCache).where(
                NutriscoreCache.product_name_key == key,
                NutriscoreCache.cached_at >= cutoff,
            )
        )
        return result.scalar_one_or_none()


async def _upsert(key: str, nutriscore: str | None, nova_group: int | None) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    stmt = (
        insert(NutriscoreCache)
        .values(product_name_key=key, nutriscore=nutriscore, nova_group=nova_group, cached_at=now)
        .on_conflict_do_update(
            index_elements=["product_name_key"],
            set_={"nutriscore": nutriscore, "nova_group": nova_group, "cached_at": now},
        )
    )
    async with session_factory() as db:
        await db.execute(stmt)
        await db.commit()


async def get_nutriscore(product_name: str) -> tuple[str | None, int | None]:
    """
    Return (nutriscore, nova_group) from DB cache or OFF API.
    Each call owns its own DB session. OFF calls are serialised (semaphore=1)
    with a short delay to stay within rate limits.
    Returns (None, None) on any error so the caller can degrade gracefully.
    """
    key = _name_key(product_name)
    if not key:
        return None, None

    try:
        cached = await _fetch_from_db(key)
        if cached is not None:
            return cached.nutriscore, cached.nova_group

        async with _SEMAPHORE:
            await asyncio.sleep(_DELAY_S)
            grade, nova = await get_nutriscore_by_name(product_name)

        await _upsert(key, grade, nova)
        return grade, nova
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nutriscore lookup failed for %r: %s", product_name, exc)
        return None, None
