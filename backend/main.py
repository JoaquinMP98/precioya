import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import compare_router, search_router
from core.config import settings
from db.database import init_db

logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="PrecioYa API",
    description="Compare supermarket prices across Mercadona, Lidl, Alcampo and Supercor.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(search_router, prefix="/api/v1", tags=["search"])
app.include_router(compare_router, prefix="/api/v1", tags=["compare"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
