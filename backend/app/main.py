"""FastAPI application entry point.

Loaded by uvicorn (`uvicorn app.main:app`). Creates the FastAPI app,
configures CORS for the frontend, and registers all routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth_routes, portfolio_routes, universe_routes


app = FastAPI(
    title="Portfolio Builder API",
    description="Markowitz MVO + Monte Carlo portfolio construction",
    version="0.1.0",
)

# CORS — allow the Vite dev server to call us during development.
# In production we'd restrict to the deployed origin.
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
