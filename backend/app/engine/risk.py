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
    # Fail fast on non-numeric columns — no silent coercion.
    for col in returns.columns:
        if not pd.api.types.is_numeric_dtype(returns[col]):
            raise ValueError("estimate_covariance requires numeric columns")

    # Drop all-NaN columns first so dropna(how='any') doesn't erase every row.
    all_nan_cols = [c for c in returns.columns if returns[c].isna().all()]
    clean_returns = returns.drop(columns=all_nan_cols)
    clean_returns = clean_returns.dropna(how="any")

    n_tickers = clean_returns.shape[1]
    n_observations = clean_returns.shape[0]
    dropped_tickers = [str(c) for c in all_nan_cols]

    if n_tickers < MIN_TICKERS:
        raise ValueError(
            f"estimate_covariance requires at least {MIN_TICKERS} tickers after cleaning"
        )
    if n_observations < MIN_OBSERVATIONS:
        raise ValueError(
            f"estimate_covariance requires at least {MIN_OBSERVATIONS} observations after cleaning"
        )

    metadata = {
        "method": "ledoit_wolf",
        "n_tickers": n_tickers,
        "n_observations": n_observations,
        "dropped_tickers": dropped_tickers,
        "fallback_used": False,
        "fallback_reason": None,
    }

    try:
        lw = LedoitWolf().fit(clean_returns.values)
        daily_cov = lw.covariance_
        shrinkage = float(lw.shrinkage_)
        if not np.all(np.isfinite(daily_cov)):
            raise RuntimeError("LedoitWolf produced non-finite covariance")
    except Exception as exc:
        logger.warning(
            "estimate_covariance fallback to sample cov: %s: %s",
            type(exc).__name__, exc,
        )
        daily_cov = clean_returns.cov().values
        shrinkage = 0.0
        metadata["method"] = "sample_fallback"
        metadata["fallback_used"] = True
        metadata["fallback_reason"] = f"{type(exc).__name__}: {exc}"

    cov_matrix = daily_cov * TRADING_DAYS_PER_YEAR

    min_eig = float(np.linalg.eigvalsh(cov_matrix).min())
    if min_eig < PSD_TOLERANCE:
        logger.warning(
            "estimate_covariance produced non-PSD matrix (min eigenvalue %.3e)", min_eig
        )

    logger.info(
        "covariance_estimated method=%s n_tickers=%d n_obs=%d shrinkage=%.4f dropped=%d fallback=%s",
        metadata["method"], n_tickers, n_observations, shrinkage,
        len(dropped_tickers), metadata["fallback_used"],
    )

    return cov_matrix, shrinkage, metadata
