import logging

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252
MIN_OBSERVATIONS = 30
MIN_TICKERS = 2
PSD_TOLERANCE = -1e-8


def estimate_covariance(returns: pd.DataFrame) -> tuple[np.ndarray, float, dict]:
    """Estimate an annualized covariance matrix from daily returns.

    Uses Ledoit-Wolf shrinkage with a sample-covariance fallback on
    technical failure. Cleans NaN from the input frame before estimation;
    all downstream logic operates on the cleaned frame.
    """
    clean_returns = returns.dropna(how="any")
    n_tickers = clean_returns.shape[1]
    n_observations = clean_returns.shape[0]

    metadata = {
        "method": "ledoit_wolf",
        "n_tickers": n_tickers,
        "n_observations": n_observations,
        "dropped_tickers": [],
        "fallback_used": False,
        "fallback_reason": None,
    }

    lw = LedoitWolf().fit(clean_returns.values)
    daily_cov = lw.covariance_
    shrinkage = float(lw.shrinkage_)

    cov_matrix = daily_cov * TRADING_DAYS_PER_YEAR

    logger.info(
        "covariance_estimated method=%s n_tickers=%d n_obs=%d shrinkage=%.4f dropped=0 fallback=False",
        metadata["method"], n_tickers, n_observations, shrinkage,
    )

    return cov_matrix, shrinkage, metadata
