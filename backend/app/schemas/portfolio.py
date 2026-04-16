from pydantic import BaseModel


class HoldingResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str
    allocation_pct: float
    expected_return: float


class SimulationResponse(BaseModel):
    percentile_10: float
    percentile_50: float
    percentile_90: float
    return_low: float
    return_high: float
    initial_value: float
    horizon_years: float
    n_simulations: int


class PortfolioResponse(BaseModel):
    id: str
    status: str
    risk_score: float
    expected_return_low: float
    expected_return_high: float
    portfolio_return: float
    total_value: float
    holdings: list[HoldingResponse]
    simulation: SimulationResponse

    model_config = {"from_attributes": True}


class PortfolioListItem(BaseModel):
    id: str
    status: str
    risk_score: float
    expected_return_low: float
    expected_return_high: float
    total_value: float
    created_at: str
