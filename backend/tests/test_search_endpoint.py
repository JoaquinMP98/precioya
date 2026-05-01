from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from scrapers.base import ScrapedProduct


def make_product(name: str, price: float, supermarket: str = "mercadona") -> ScrapedProduct:
    return ScrapedProduct(
        name=name,
        price=price,
        url=f"https://example.com/{name}",
        supermarket=supermarket,
        price_per_unit=f"{price} €/ud",
        image_url="https://example.com/img.jpg",
    )


MOCK_PRODUCTS = [
    make_product("Leche entera 1L", 0.65),
    make_product("Leche semidesnatada 1L", 0.62),
]


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def patched_service():
    with patch("api.routes.search.search_with_cache", new_callable=AsyncMock) as mock:
        mock.return_value = (MOCK_PRODUCTS, False, [])
        yield mock


# ---- happy path ----

def test_search_returns_results_sorted_by_price(client, patched_service):
    resp = client.get("/api/v1/search?q=leche")
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "leche"
    assert body["total"] == 2
    prices = [r["price"] for r in body["results"]]
    assert prices == sorted(prices)


def test_search_includes_all_fields(client, patched_service):
    first = client.get("/api/v1/search?q=leche").json()["results"][0]
    for field in ("name", "price", "supermarket", "url", "price_per_unit", "image_url"):
        assert field in first


def test_search_from_cache_false_on_live_scrape(client, patched_service):
    body = client.get("/api/v1/search?q=leche").json()
    assert body["from_cache"] is False


def test_search_from_cache_true_when_cached(client):
    with patch("api.routes.search.search_with_cache", new_callable=AsyncMock) as mock:
        mock.return_value = (MOCK_PRODUCTS, True, [])
        body = client.get("/api/v1/search?q=leche").json()
    assert body["from_cache"] is True


def test_search_respects_limit(client, patched_service):
    patched_service.return_value = (
        [make_product(f"Product {i}", float(i)) for i in range(50)],
        False,
        [],
    )
    assert len(client.get("/api/v1/search?q=leche&limit=5").json()["results"]) == 5


# ---- validation ----

def test_search_query_too_short_returns_422(client):
    assert client.get("/api/v1/search?q=a").status_code == 422


def test_search_missing_query_returns_422(client):
    assert client.get("/api/v1/search").status_code == 422


# ---- failure handling ----

def test_search_scraper_failure_returns_warning(client):
    with patch("api.routes.search.search_with_cache", new_callable=AsyncMock) as mock:
        mock.return_value = ([], False, ["mercadona: timed out after 10.0s"])
        resp = client.get("/api/v1/search?q=leche")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert any("timed out" in w for w in body["warnings"])


def test_search_empty_results(client, patched_service):
    patched_service.return_value = ([], False, [])
    body = client.get("/api/v1/search?q=xyzzy").json()
    assert body["total"] == 0
    assert body["results"] == []


# ---- health ----

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
