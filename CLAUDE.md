# PrecioYa — Project Context for Claude

## What is this?

PrecioYa is a Spanish supermarket price comparator. Users search for a product and get prices across Mercadona, Lidl, Alcampo, and Supercor in real time (or from a recent cache). The goal is to be fast, accurate, and mobile-first.

## Stack

| Layer | Tech |
|-------|------|
| Backend API | Python 3.12, FastAPI |
| Scraping | Playwright (headless Chromium) |
| Database | SQLite (via SQLAlchemy + aiosqlite) |
| Mobile | React Native + Expo (TypeScript) |
| State management | Zustand |
| Navigation | Expo Router |

## Repo layout

```
precioya/
├── backend/
│   ├── api/
│   │   ├── routes/          # FastAPI routers (products, supermarkets, search)
│   │   └── schemas/         # Pydantic request/response models
│   ├── scrapers/
│   │   ├── base.py          # Abstract BaseScraper
│   │   ├── mercadona/
│   │   ├── lidl/
│   │   ├── alcampo/
│   │   └── supercor/
│   ├── db/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   ├── database.py      # Engine + session factory
│   │   └── migrations/      # Alembic migration scripts
│   ├── core/
│   │   ├── config.py        # Settings (env vars via pydantic-settings)
│   │   ├── scheduler.py     # APScheduler jobs for nightly scrapes
│   │   └── cache.py         # TTL-based price cache logic
│   ├── tests/
│   ├── main.py              # FastAPI app entry point
│   └── requirements.txt
├── mobile/
│   ├── src/
│   │   ├── screens/         # Search, ProductDetail, Comparison, Settings
│   │   ├── components/      # PriceCard, SupermarketBadge, SearchBar, etc.
│   │   ├── hooks/           # useSearch, usePrices, useStore
│   │   ├── services/        # API client (axios)
│   │   ├── navigation/      # Expo Router layout files
│   │   ├── store/           # Zustand stores
│   │   └── utils/           # formatPrice, formatDate, etc.
│   ├── assets/
│   ├── app.json
│   ├── package.json
│   └── tsconfig.json
├── scripts/
│   ├── seed_db.py           # Populate DB with test products
│   └── run_scrapers.py      # Manual scrape trigger
├── .github/workflows/
│   └── scrape.yml           # Nightly scrape CI job
├── .env.example
└── CLAUDE.md
```

## Domain model

```
Supermarket (id, name, slug, base_url, logo_url)
Product     (id, name, slug, brand, category, barcode)
Price       (id, product_id, supermarket_id, price, unit, scraped_at)
```

Prices are re-scraped every 24 h. Searches match against `Product.name` (FTS5) and return the latest `Price` row per supermarket.

## Scrapers

Each scraper lives in `backend/scrapers/<chain>/scraper.py` and implements `BaseScraper`:

```python
class BaseScraper(ABC):
    async def search(self, query: str) -> list[ScrapedProduct]: ...
    async def get_product(self, url: str) -> ScrapedProduct: ...
```

Playwright is used in async mode. Each scraper gets its own browser context. Rate-limit: 1 req/s, randomised UA, no stealth plugins (avoid overkill until actually blocked).

## API surface

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search?q=&limit=` | Search products across all supermarkets |
| GET | `/products/{id}` | Single product with price history |
| GET | `/supermarkets` | List supported supermarkets |
| GET | `/prices/compare?product_ids=` | Side-by-side price table |
| POST | `/admin/scrape` | Trigger manual scrape (admin key required) |

## Key conventions

- **Python**: async everywhere (FastAPI + asyncio). Ruff for linting/formatting. Type hints mandatory.
- **TypeScript**: strict mode on. No `any`. Component files are PascalCase, utilities are camelCase.
- **Prices**: always stored and returned in euros as `float` (2 decimal places). No currency conversion.
- **Error handling**: scrapers never raise to the API layer — they return empty lists and log the error. The API never returns 500 for a failed scraper; it returns partial results with a `warnings` field.
- **Testing**: pytest + pytest-asyncio for backend. Unit-test scrapers against saved HTML fixtures, not live sites.

## Environment variables

```
DATABASE_URL=sqlite+aiosqlite:///./precioya.db
ADMIN_API_KEY=changeme
LOG_LEVEL=INFO
PLAYWRIGHT_HEADLESS=true
```

## Running locally

```bash
# Backend
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload

# Mobile
cd mobile
npm install
npx expo start
```

## Supermarket scraper notes

| Chain | Auth required | Notes |
|-------|--------------|-------|
| Mercadona | No | JSON API at `tienda.mercadona.es/api` — prefer over scraping HTML |
| Lidl | No | Product pages are SPA; wait for `.product-grid-box` |
| Alcampo | No | Standard HTML, easy to scrape |
| Supercor | No | El Corte Inglés infrastructure, heavier JS; increase timeout to 15s |
