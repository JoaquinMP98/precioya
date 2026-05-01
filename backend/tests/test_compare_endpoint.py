from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from scrapers.base import ScrapedProduct


def make_product(name: str, price: float, supermarket: str) -> ScrapedProduct:
    return ScrapedProduct(
        name=name,
        price=price,
        url=f"https://example.com/{supermarket}/{name}",
        supermarket=supermarket,
        price_per_unit=f"{price} €/L",
        image_url="https://example.com/img.jpg",
    )


MULTI_MARKET = [
    make_product("Leche entera 1L", 0.65, "mercadona"),
    make_product("Leche semidesnatada 1L", 0.62, "mercadona"),
    make_product("Leche fresca 1L", 0.58, "lidl"),
    make_product("Leche UHT 1L", 0.70, "alcampo"),
]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def patched_service(request):
    products = getattr(request, "param", MULTI_MARKET)
    with patch("api.routes.compare.search_with_cache", new_callable=AsyncMock) as mock:
        mock.return_value = (products, False, [])
        yield mock


# ---- shape ----

def test_compare_response_shape(client, patched_service):
    resp = client.get("/api/v1/compare?q=leche")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("query", "cheapest", "by_supermarket", "from_cache", "warnings"):
        assert key in body


def test_compare_cheapest_is_global_minimum(client, patched_service):
    resp = client.get("/api/v1/compare?q=leche")
    cheapest = resp.json()["cheapest"]
    assert cheapest["price"] == 0.58
    assert cheapest["supermarket"] == "lidl"


def test_compare_one_entry_per_supermarket(client, patched_service):
    resp = client.get("/api/v1/compare?q=leche")
    by_market = resp.json()["by_supermarket"]
    supermarkets = [r["supermarket"] for r in by_market]
    assert len(supermarkets) == len(set(supermarkets))  # no duplicates


def test_compare_by_supermarket_sorted_by_price(client, patched_service):
    resp = client.get("/api/v1/compare?q=leche")
    prices = [r["price"] for r in resp.json()["by_supermarket"]]
    assert prices == sorted(prices)


def test_compare_picks_cheapest_within_each_market(client, patched_service):
    resp = client.get("/api/v1/compare?q=leche")
    by_market = {r["supermarket"]: r for r in resp.json()["by_supermarket"]}
    # Mercadona has two products (0.65 and 0.62) — should pick 0.62
    assert by_market["mercadona"]["price"] == 0.62


# ---- edge cases ----

def test_compare_no_results(client):
    with patch("api.routes.compare.search_with_cache", new_callable=AsyncMock) as mock:
        mock.return_value = ([], False, [])
        resp = client.get("/api/v1/compare?q=xyzzy")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cheapest"] is None
    assert body["by_supermarket"] == []


def test_compare_with_warnings(client):
    with patch("api.routes.compare.search_with_cache", new_callable=AsyncMock) as mock:
        mock.return_value = ([], False, ["lidl: timed out after 10.0s"])
        resp = client.get("/api/v1/compare?q=leche")
    assert resp.status_code == 200
    assert len(resp.json()["warnings"]) == 1


def test_compare_from_cache_flag(client):
    with patch("api.routes.compare.search_with_cache", new_callable=AsyncMock) as mock:
        mock.return_value = (MULTI_MARKET, True, [])
        resp = client.get("/api/v1/compare?q=leche")
    assert resp.json()["from_cache"] is True


def test_compare_query_too_short(client):
    resp = client.get("/api/v1/compare?q=a")
    assert resp.status_code == 422
