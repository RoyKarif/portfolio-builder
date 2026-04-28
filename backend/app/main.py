"""FastAPI application entry point.

Loaded by uvicorn (`uvicorn app.main:app`). Creates the FastAPI app,
configures CORS for the frontend, and registers all routers.

Lifespan hook (`startup_universe`) auto-registers the 20 curated Asset
rows on boot, so the universe API always returns them — no manual
seed step required. Prices are fetched lazily by the build endpoint
when the user actually needs them.
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth_routes, portfolio_routes, universe_routes
from app.data import asset_repo
from app.data.universe_definition import CURATED_UNIVERSE
from app.db import SessionLocal


log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup and shutdown hooks.

    Startup: register Asset rows for the curated universe (idempotent).
    No prices are fetched here — that happens lazily on first build,
    in parallel, with synthetic fallback if yfinance is down.
    """
    db = SessionLocal()
    created = 0
    try:
        for ticker, name, asset_class in CURATED_UNIVERSE:
            existing = asset_repo.get_asset_by_ticker(db, ticker)
            if existing is None:
                asset_repo.create_asset(
                    db,
                    ticker=ticker,
                    name=name,
                    asset_class=asset_class,
                    is_curated=True,
                )
                created += 1
        if created > 0:
            log.info("Registered %d new curated assets at startup", created)
    except Exception as e:
        log.warning("Could not initialize curated universe at startup: %s", e)
    finally:
        db.close()
    yield
    # No shutdown work needed.


app = FastAPI(
    title="Portfolio Builder API",
    description="Markowitz MVO + Monte Carlo portfolio construction",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the Vite dev server to call us during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness probe. Returns 200 if the app is running."""
    return {"status": "ok"}


# Register routers.
app.include_router(auth_routes.router)
app.include_router(universe_routes.router)
app.include_router(portfolio_routes.router)
