import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scrapers.mercadona.scraper import MercadonaScraper, _parse_product

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


# --- unit tests for _parse_product ---

def test_parse_product_full():
    raw = load_fixture("mercadona_search.json")["results"]["products"][0]
    product = _parse_product(raw)

    assert product is not None
    assert product.name == "Leche entera Hacendado brick 1 L"
    assert product.price == 0.65
    assert product.price_per_unit == "0.65 €/L"
    assert product.image_url is not None
    assert product.url == "https://tienda.mercadona.es/product/7543"
    assert product.supermarket == "mercadona"
    assert product.brand == "Hacendado"
    assert product.category == "Lácteos y huevos"


def test_parse_product_missing_price_returns_none():
    raw = load_fixture("mercadona_search.json")["results"]["products"][2]
    assert _parse_product(raw) is None


def test_parse_product_no_photos():
    raw = load_fixture("mercadona_search.json")["results"]["products"][1]
    raw = {**raw, "photos": []}
    product = _parse_product(raw)
    assert product is not None
    assert product.image_url is None


# --- integration-style tests using mocked HTTP ---

@pytest.fixture
def scraper():
    return MercadonaScraper()


@pytest.mark.asyncio
async def test_search_returns_parsed_products(scraper):
    fixture = load_fixture("mercadona_search.json")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = fixture

    with patch("scrapers.mercadona.scraper.httpx.AsyncClient") as mock_client_cls, \
         patch("scrapers.mercadona.scraper.asyncio.sleep", new_callable=AsyncMock):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await scraper.search("leche")

    # Product with missing price (id 9999) must be filtered out
    assert len(results) == 2
    assert all(p.supermarket == "mercadona" for p in results)
    assert results[0].price == 0.65
    assert results[1].price == 0.62


@pytest.mark.asyncio
async def test_search_returns_empty_on_http_error(scraper):
    import httpx

    with patch("scrapers.mercadona.scraper.httpx.AsyncClient") as mock_client_cls, \
         patch("scrapers.mercadona.scraper.asyncio.sleep", new_callable=AsyncMock):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        results = await scraper.search("leche")

    assert results == []


@pytest.mark.asyncio
async def test_get_product_invalid_url_returns_none(scraper):
    result = await scraper.get_product("https://tienda.mercadona.es/product/not-an-id")
    assert result is None
