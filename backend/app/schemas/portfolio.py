"""Portfolio-related request/response schemas."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class AssetResponse(BaseModel):
    """One row in the universe response."""

    ticker: str
    name: str
    asset_class: str
    is_curated: bool

    model_config = {"from_attributes": True}


class PortfolioBuildRequest(BaseModel):
    """Body of POST /api/portfolios/build."""

    # Sensible bounds. We allow up to $10M to keep CHECK-style validation
    # client-side without offending high-net-worth demos.
    amount: Decimal = Field(gt=0, le=10_000_000, decimal_places=2)

    risk_level: int = Field(ge=1, le=5)
    horizon_years: int = Field(ge=1, le=30)

    # Tickers the user selected (curated minus excluded plus added customs).
    # Min 2 because a 1-asset portfolio can't be diversified.
    tickers: list[str] = Field(min_length=2, max_length=30)

    # Optional name; if absent, the route generates one ("Portfolio #N").
    name: str | None = Field(default=None, max_length=255)


class TimelinePoint(BaseModel):
    year: int
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class MCSummary(BaseModel):
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float
    var_5: float
    timeline: list[TimelinePoint]


class HistogramData(BaseModel):
    counts: list[int]
    edges: list[float]


class PortfolioResponse(BaseModel):
    """Full portfolio detail returned by /build, /list (per-row), and /detail."""

    id: int
    name: str
    created_at: datetime

    # Inputs
    amount: Decimal
    risk_level: int
    horizon_years: int
    target_volatility: Decimal

    # Outputs
    weights: dict[str, float]
    expected_return: Decimal
    expected_volatility: Decimal
    sharpe_ratio: Decimal
    mc_summary: MCSummary
    mc_seed: int

    # Optional histogram (computed on demand to keep list responses small).
    histogram: HistogramData | None = None

    model_config = {"from_attributes": True}


class PortfolioListItem(BaseModel):
    """Lightweight version used in GET /portfolios (the list view)."""

    id: int
    name: str
    created_at: datetime
    amount: Decimal
    risk_level: int
    horizon_years: int
    expected_return: Decimal
    expected_volatility: Decimal

    model_config = {"from_attributes": True}
