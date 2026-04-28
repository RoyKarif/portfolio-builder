"""FastAPI application entry point.

This is what uvicorn loads (`uvicorn app.main:app`). It creates the
FastAPI instance, attaches middleware, and registers routers.

In Step 2 (current state), this is minimal: just a /health endpoint
to verify the backend boots. Routers for auth/portfolios/universe
will be added in Step 7.
"""

from fastapi import FastAPI


app = FastAPI(
    title="Portfolio Builder API",
    description="Markowitz MVO + Monte Carlo portfolio construction",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    """Liveness probe. Returns 200 if the app is running.

    Used by:
      - docker-compose / kubernetes (production) for restart policies
      - manually by developers ("is the backend up?")
      - CI smoke tests
    """
    return {"status": "ok"}
