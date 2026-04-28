"""Compute the two statistical quantities that drive the entire system:
μ (expected returns vector) and Σ (covariance matrix).

Both are estimated from historical log-returns. We multiply by the
number of trading days per year (252) to annualize.

Why 252? It's the conventional count of trading days in a US year
(365 days minus weekends minus ~10 holidays). Standard in industry.
If you ever swap to monthly data, change this to 12.
"""

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def mean_returns(
    log_returns: pd.DataFrame,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> np.ndarray:
    """Estimate μ — the vector of annualized expected returns.

    For each ticker, we take the simple mean of its daily log-returns
    and multiply by 252. This treats log-returns as i.i.d. — a strong
    assumption (real returns have time-varying volatility), but standard
    in introductory portfolio theory.

    Returns: 1-D numpy array of shape (N,) where N = number of tickers.
             The order matches log_returns.columns.
    """
    return log_returns.mean().values * periods_per_year


def covariance_matrix(
    log_returns: pd.DataFrame,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> np.ndarray:
    """Estimate Σ — the annualized N×N covariance matrix.

    Σ[i,j] = covariance between asset i and asset j.

    Diagonal entries (i==j) are individual variances:
        σ²_i = E[(r_i - μ_i)²]

    Off-diagonal entries capture co-movement:
        - Positive: assets move together.
        - Negative: assets move oppositely (good for diversification).
        - Zero: independent.

    pandas `cov()` uses the unbiased sample covariance:
        (1 / (n-1)) * sum_t (r_t - r̄) (r_t - r̄)ᵀ

    We multiply by 252 because var(sum of i.i.d.) = N * var(single)
    when there's no autocorrelation. The square-root of the diagonal
    gives annualized volatility (so for SPY, sqrt(Σ[SPY,SPY]) ≈ 0.16).
    """
    return log_returns.cov().values * periods_per_year
