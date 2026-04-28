"""Math engine — pure computational layer.

No DB, no HTTP, no ORM. Functions take numpy arrays / pandas DataFrames
and return numpy arrays / dicts. This isolation makes the engine
testable in isolation and easier to reason about.
"""

from app.engine.returns import daily_log_returns
from app.engine.statistics import mean_returns, covariance_matrix
from app.engine.mvo import solve_mvo, RISK_LEVEL_TO_VOLATILITY
from app.engine.monte_carlo import simulate_portfolio, summarize

__all__ = [
    "daily_log_returns",
    "mean_returns",
    "covariance_matrix",
    "solve_mvo",
    "RISK_LEVEL_TO_VOLATILITY",
    "simulate_portfolio",
    "summarize",
]
