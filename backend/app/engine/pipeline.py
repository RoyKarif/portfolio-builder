from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

from app.engine.universe import select_universe
from app.engine.predictor import predict_returns
from app.engine.optimizer import optimize_portfolio
from app.engine.simulator import run_monte_carlo
from app.engine.risk import estimate_covariance
from app.engine.screens import apply_quality_screen

HORIZON_YEARS = {
    "6m": 0.5,
    "1-3y": 2.0,
    "3-5y": 4.0,
    "5y+": 7.0,
}


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

    # Stage 3: Markowitz Optimization
    # Note: profile.target_return is collected but not currently consumed
    # by the optimizer. Field is preserved on the profile for a future
    # "target return" feature.
    opt_result = optimize_portfolio(
        tickers=valid_tickers,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        risk_level=risk_level,
    )

    # Stage 4: Monte Carlo Simulation
    horizon_years = HORIZON_YEARS.get(investment_horizon, 3.0)
    weights_array = np.array([opt_result["weights"].get(t, 0) for t in valid_tickers])

    sim_result = run_monte_carlo(
        weights=weights_array,
        expected_returns=valid_returns,
        cov_matrix=cov_matrix,
        initial_value=available_amount,
        horizon_years=horizon_years,
    )

    holdings = []
    for ticker in valid_tickers:
        w = opt_result["weights"].get(ticker, 0)
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
        "risk_score": round(opt_result["portfolio_volatility"] * 100, 2),
        "expected_return_low": round(sim_result["return_low"] * 100, 2),
        "expected_return_high": round(sim_result["return_high"] * 100, 2),
        "portfolio_return": round(opt_result["portfolio_return"] * 100, 2),
        "simulation": sim_result,
        "status": opt_result["status"],
        "covariance_method": cov_meta["method"],
        "shrinkage_intensity": round(shrinkage, 4),
    }
