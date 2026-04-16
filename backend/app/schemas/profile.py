import uuid
from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    risk_level: int = Field(ge=1, le=5)
    investment_horizon: str
    available_amount: float = Field(gt=0)
    target_return: float = Field(gt=0, le=100)
    preferred_sectors: list[str] = []
    include_tickers: list[str] = []
    exclude_tickers: list[str] = []


class ProfileResponse(BaseModel):
    id: str
    risk_level: int
    investment_horizon: str
    available_amount: float
    target_return: float
    preferred_sectors: list[str]
    include_tickers: list[str]
    exclude_tickers: list[str]

    model_config = {"from_attributes": True}
