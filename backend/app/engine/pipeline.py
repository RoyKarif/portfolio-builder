import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from app.engine.universe import select_universe
from app.engine.predictor import predict_returns
from app.engine.optimizer import optimize_portfolio, RISK_VOLATILITY_CAP
from app.engine.simulator import run_monte_carlo
from app.engine.risk import estimate_covariance
from app.engine.screens import apply_quality_screen
from app.engine.hrp import hrp_weights

logger = logging.getLogger(__name__)

HORIZON_YEARS = {
    "6m": 0.5,
    "1-3y": 2.0,
    "3-5y": 4.0,
    "5y+": 7.0,
}

# Product decision, not a mathematical truth — accept HRP if it's within
# 10% of the user's risk cap. Tune after observing real-world drift.
HRP_VOL_TOLERANCE = 1.10


def generate_portfolio(
    country: str,
    risk_level: int,
    investment_horizon: str,
    available_amount: float,
    target_return: float,
    preferred_sectors: list[str],
    include_tickers: list[str],
    exclude_tickers: list[str],
    db,
) -> dict:
    # Stage 1: Universe Selection
    stocks = select_universe(
        country=country,
        sectors=preferred_sectors,
        include_tickers=include_tickers,
        exclude_tickers=exclude_tickers,
    )

    if len(stocks) < 5:
        return {"error": "Not enough stocks found. Try broadening your sector selection."}

    tickers = [s["ticker"] for s in stocks]
    snapshot_date = (datetime.utcnow() - timedelta(days=1)).date()
    end_date = snapshot_date.isoformat()
    start_date_3y = (snapshot_date - timedelta(days=3 * 365)).isoformat()
    cov_cutoff = snapshot_date - timedelta(days=2 * 365)

    # Single batch download covers both ML training (3yr) and cov matrix (2yr slice).
    batch = yf.download(
        tickers, start=start_date_3y, end=end_date,
        progress=False, auto_adjust=True, group_by="ticker", threads=True,
    )

    # Stage 2: ML Prediction (reuses the batch above)
    stocks = predict_returns(stocks, batch=batch, db=db)

    price_data, dropped_by_screen = apply_quality_screen(batch, tickers, cov_cutoff)
    valid_tickers = list(price_data.keys())
    if len(valid_tickers) < 5:
        return {"error": "Not enough historical data available."}

    prices_df = pd.DataFrame(price_data).dropna()
    returns_df = prices_df.pct_change().dropna()

    try:
        cov_matrix, shrinkage, cov_meta = estimate_covariance(returns_df)
    except ValueError:
        return {"error": "Not enough historical data available."}

    # Realign every ticker-ordered structure to the cleaned ticker set
    # before handing anything to the optimizer.
    if cov_meta["dropped_tickers"]:
        dropped = set(cov_meta["dropped_tickers"])
        valid_tickers = [t for t in valid_tickers if t not in dropped]
        if len(valid_tickers) < 5:
            return {"error": "Not enough historical data available."}

    ticker_to_stock = {s["ticker"]: s for s in stocks}
    valid_stocks = [ticker_to_stock[t] for t in valid_tickers]
    valid_returns = np.array([s["expected_return"] for s in valid_stocks])

    # Stage 3: Portfolio construction (HRP default, MVO fallback)
    target_vol = RISK_VOLATILITY_CAP[risk_level]
    weighting_method: str
    optimizer_status: str | None = None
    hrp_candidate_vol: float | None = None
    hrp_error: str | None = None

    try:
        hrp_w = hrp_weights(cov_matrix, valid_tickers)
        hrp_arr = np.array([hrp_w[t] for t in valid_tickers])
        # cov_matrix is annualized inside estimate_covariance, so
        # sqrt(w @ cov_matrix @ w) is annualized vol directly.
        hrp_candidate_vol = float(np.sqrt(hrp_arr @ cov_matrix @ hrp_arr))

        if hrp_candidate_vol <= target_vol * HRP_VOL_TOLERANCE:
            weights_array = hrp_arr
            weighting_method = "hrp"
            portfolio_vol = hrp_candidate_vol
            portfolio_return = float(hrp_arr @ valid_returns)
        else:
            opt_result = optimize_portfolio(
                tickers=valid_tickers,
                expected_returns=valid_returns,
                cov_matrix=cov_matrix,
                risk_level=risk_level,
            )
            weights_array = np.array([opt_result["weights"].get(t, 0) for t in valid_tickers])
            # optimize_portfolio rounds weights to 4 decimals before returning,
            # so the sum can drift by up to n × 5e-5. Renormalize so the
            # post-block assertion stays strict.
            weights_array = weights_array / weights_array.sum()
            optimizer_status = opt_result["status"]
            weighting_method = (
                "fallback_equal_weight"
                if optimizer_status == "fallback_equal_weight"
                else "mvo_risk_cap"
            )
            portfolio_vol = opt_result["portfolio_volatility"]
            portfolio_return = opt_result["portfolio_return"]
    except ValueError as e:
        hrp_error = str(e)
        opt_result = optimize_portfolio(
            tickers=valid_tickers,
            expected_returns=valid_returns,
            cov_matrix=cov_matrix,
            risk_level=risk_level,
        )
        weights_array = np.array([opt_result["weights"].get(t, 0) for t in valid_tickers])
        weights_array = weights_array / weights_array.sum()  # see comment above
        optimizer_status = opt_result["status"]
        weighting_method = (
            "fallback_equal_weight"
            if optimizer_status == "fallback_equal_weight"
            else "mvo_fallback_hrp_error"
        )
        portfolio_vol = opt_result["portfolio_volatility"]
        portfolio_return = opt_result["portfolio_return"]

    assert abs(weights_array.sum() - 1.0) < 1e-8, "weights must sum to 1 before sim"

    logger.info(
        "portfolio_construction",
        extra={
            "hrp_candidate_vol": hrp_candidate_vol,
            "hrp_error": hrp_error,
            "target_vol": target_vol,
            "tolerance": HRP_VOL_TOLERANCE,
            "weighting_method": weighting_method,
            "optimizer_status": optimizer_status,
        },
    )

    # Stage 4: Monte Carlo Simulation
    horizon_years = HORIZON_YEARS.get(investment_horizon, 3.0)

    sim_result = run_monte_carlo(
        weights=weights_array,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        initial_value=available_amount,
        horizon_years=horizon_years,
    )

    holdings = []
    for i, ticker in enumerate(valid_tickers):
        w = float(weights_array[i])
        if w < 0.01:
            continue
        stock = ticker_to_stock[ticker]
        holdings.append({
            "ticker": ticker,
            "company_name": stock["company_name"],
            "sector": stock["sector"],
            "allocation_pct": round(w * 100, 2),
            "expected_return": round(stock["expected_return"] * 100, 2),
        })

    return {
        "holdings": holdings,
        "risk_score": round(portfolio_vol * 100, 2),
        "expected_return_low": round(sim_result["return_low"] * 100, 2),
        "expected_return_high": round(sim_result["return_high"] * 100, 2),
        "portfolio_return": round(portfolio_return * 100, 2),
        "simulation": sim_result,
        "status": optimizer_status if optimizer_status is not None else "hrp",
        "covariance_method": cov_meta["method"],
        "shrinkage_intensity": round(shrinkage, 4),
        "weighting_method": weighting_method,
        "optimizer_status": optimizer_status,
        "hrp_candidate_vol": hrp_candidate_vol,
    }
