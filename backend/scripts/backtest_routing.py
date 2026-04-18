"""Walk-forward backtest of HRP / MVO / hybrid / equal-weight on realized returns.

Pulls ~7 years of daily prices for a fixed universe (top US tech +
defensive ETFs). Annual rebalancing: at each year-start, fit cov + μ
on the trailing 2-year window, run each strategy to produce weights,
evaluate the weights on the next 1-year window. Aggregate per-strategy
and per-risk-level metrics across all eval windows.

Strategies (per risk level 1, 3, 5):
- equal_weight: 1/N baseline (independent of risk_level)
- hrp_only:    pure HRP, no MVO fallback (independent of risk_level)
- mvo_only:    pure MVO at the given risk_level cap
- hybrid:      full P5 routing logic (HRP within band, MVO outside)

Metrics per (strategy, risk_level):
- Annualized return (geometric)
- Annualized vol (realized)
- Sharpe (rf = 0)
- Max drawdown
- For hybrid: routing distribution across rebalances

Caveats (deliberately accepted for v1):
- Sample-mean expected returns for MVO. Using the production XGBoost
  predictor would introduce training-data leakage in a backtest. HRP
  doesn't use μ so isn't affected.
- No transaction costs (annual rebalance keeps costs small but non-zero).
- Fixed universe; no point-in-time membership adjustment.
- Single universe (US tech + defensives).
- Annual rebalancing (5 obs per strategy).

Usage:
    cd backend && python scripts/backtest_routing.py
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.hrp import hrp_weights
from app.engine.optimizer import RISK_VOLATILITY_CAP, optimize_portfolio
from app.engine.pipeline import (
    HRP_LOWER_TOLERANCE,
    HRP_TOLERANCE_EPSILON,
    HRP_UPPER_TOLERANCE,
)
from app.engine.risk import estimate_covariance


UNIVERSE = [
    "MSFT", "AAPL", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "AVGO", "CSCO", "IBM",
    "AGG", "IEF", "GLD", "XLU", "XLP",
]

RISK_LEVELS = [1, 3, 5]
TRAINING_WINDOW_YEARS = 2
EVAL_WINDOW_DAYS = 252
TRADING_DAYS = 252
TOTAL_HISTORY_YEARS = 7  # 5 years of evaluation + 2-year initial training window


def fetch_prices(tickers: list[str], start: datetime, end: datetime) -> pd.DataFrame:
    """Returns DataFrame of close prices indexed by date, columns=tickers.
    Drops any ticker without full coverage over the window."""
    data = yf.download(
        tickers, start=start, end=end,
        progress=False, auto_adjust=True, group_by="ticker", threads=True,
    )
    closes = {}
    for t in tickers:
        try:
            close = data[t]["Close"] if isinstance(data.columns, pd.MultiIndex) else data["Close"]
        except KeyError:
            continue
        if close.dropna().empty:
            continue
        closes[t] = close
    df = pd.DataFrame(closes)
    # Drop tickers with significantly less coverage than the longest column
    n_max = df.notna().sum().max()
    coverage = df.notna().sum() / n_max
    keep = coverage[coverage >= 0.95].index
    df = df[keep]
    df = df.dropna()
    return df


def hybrid_route(hrp_vol: float, mvo_status: str, target_vol: float) -> str:
    """Replicates pipeline.py's P5 symmetric routing rule."""
    lower = target_vol * HRP_LOWER_TOLERANCE - HRP_TOLERANCE_EPSILON
    upper = target_vol * HRP_UPPER_TOLERANCE + HRP_TOLERANCE_EPSILON
    if lower <= hrp_vol <= upper:
        return "hrp"
    if mvo_status == "fallback_equal_weight":
        return "fallback_equal_weight"
    if hrp_vol > upper:
        return "mvo_risk_cap"
    return "mvo_underutilized"


def run_strategies(returns_train: pd.DataFrame, risk_level: int) -> dict:
    """Compute weights for all 4 strategies at this rebalance."""
    cov, _, cov_meta = estimate_covariance(returns_train)
    # estimate_covariance may drop tickers with all-NaN columns; align tickers.
    valid_tickers = [t for t in returns_train.columns if t not in cov_meta["dropped_tickers"]]
    if len(valid_tickers) < 5:
        return None
    mu = returns_train[valid_tickers].mean().values * TRADING_DAYS
    n = len(valid_tickers)

    out = {"tickers": valid_tickers}

    out["equal_weight"] = np.ones(n) / n

    try:
        hrp_w_dict = hrp_weights(cov, valid_tickers)
        out["hrp_only"] = np.array([hrp_w_dict[t] for t in valid_tickers])
    except ValueError:
        out["hrp_only"] = None

    mvo_result = optimize_portfolio(valid_tickers, mu, cov, risk_level)
    mvo_w = np.array([mvo_result["weights"].get(t, 0.0) for t in valid_tickers])
    if mvo_w.sum() > 0:
        mvo_w = mvo_w / mvo_w.sum()
    out["mvo_only"] = mvo_w
    out["mvo_status"] = mvo_result["status"]

    target_vol = RISK_VOLATILITY_CAP[risk_level]
    if out["hrp_only"] is not None:
        hrp_arr = out["hrp_only"]
        hrp_vol = float(np.sqrt(hrp_arr @ cov @ hrp_arr))
        method = hybrid_route(hrp_vol, mvo_result["status"], target_vol)
        out["hybrid"] = hrp_arr if method == "hrp" else mvo_w
    else:
        method = "mvo_fallback_hrp_error"
        out["hybrid"] = mvo_w
    out["hybrid_method"] = method

    return out


def evaluate(weights: np.ndarray, prices_eval: pd.DataFrame, tickers: list[str]) -> pd.Series:
    """Daily portfolio returns over the eval window."""
    if weights is None:
        return None
    prices_subset = prices_eval[tickers]
    asset_returns = prices_subset.pct_change().dropna()
    return asset_returns @ weights


def metrics(daily_returns: pd.Series) -> dict:
    if daily_returns is None or len(daily_returns) == 0:
        return None
    n_days = len(daily_returns)
    annual_return = float((1 + daily_returns).prod() ** (TRADING_DAYS / n_days) - 1)
    annual_vol = float(daily_returns.std() * np.sqrt(TRADING_DAYS))
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0.0
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_dd = float(drawdown.min())
    return {
        "annual_return": annual_return,
        "annual_vol": annual_vol,
        "sharpe": float(sharpe),
        "max_drawdown": max_dd,
    }


def main():
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=int(365 * TOTAL_HISTORY_YEARS))

    print(f"Fetching prices for {len(UNIVERSE)} tickers ({start_date} to {end_date})...")
    prices = fetch_prices(UNIVERSE, start_date, end_date)
    if prices.empty:
        print("ERROR: no price data fetched")
        return
    print(f"Got {len(prices)} trading days, {len(prices.columns)} tickers retained "
          f"after coverage filter ({sorted(prices.columns)}).")

    earliest_eval = prices.index[0] + pd.DateOffset(years=TRAINING_WINDOW_YEARS)
    rebalance_dates = []
    cursor = earliest_eval
    while cursor + pd.Timedelta(days=EVAL_WINDOW_DAYS) <= prices.index[-1]:
        idx = prices.index.searchsorted(cursor)
        if idx < len(prices.index):
            rebalance_dates.append(prices.index[idx])
        cursor = cursor + pd.DateOffset(years=1)

    print(f"Rebalance dates: {len(rebalance_dates)} — {[d.date() for d in rebalance_dates]}")
    print()

    results = {}
    routing_log = []

    for risk_level in RISK_LEVELS:
        for rebal_date in rebalance_dates:
            train_start = rebal_date - pd.DateOffset(years=TRAINING_WINDOW_YEARS)
            eval_end_pos = min(prices.index.searchsorted(rebal_date) + EVAL_WINDOW_DAYS, len(prices.index) - 1)
            eval_end = prices.index[eval_end_pos]

            prices_train = prices.loc[train_start:rebal_date]
            prices_eval = prices.loc[rebal_date:eval_end]
            returns_train = prices_train.pct_change().dropna()

            if len(returns_train) < 100:
                continue

            strats = run_strategies(returns_train, risk_level)
            if strats is None:
                continue

            for strat in ["equal_weight", "hrp_only", "mvo_only", "hybrid"]:
                weights = strats[strat]
                daily = evaluate(weights, prices_eval, strats["tickers"])
                if daily is not None and len(daily) > 0:
                    results.setdefault((strat, risk_level), []).append(daily)

            routing_log.append({
                "risk_level": risk_level,
                "date": rebal_date.date(),
                "method": strats["hybrid_method"],
            })

    print("=" * 84)
    print("TABLE A — Per-strategy annualized metrics across all eval windows")
    print("=" * 84)
    print(f"{'strategy':<15} {'risk':>5} {'annual_ret':>12} {'annual_vol':>12} {'sharpe':>8} {'max_dd':>10}")
    print("-" * 84)
    for risk_level in RISK_LEVELS:
        for strat in ["equal_weight", "hrp_only", "mvo_only", "hybrid"]:
            key = (strat, risk_level)
            if key not in results:
                print(f"{strat:<15} {risk_level:>5}     (no data)")
                continue
            all_returns = pd.concat(results[key])
            m = metrics(all_returns)
            print(
                f"{strat:<15} {risk_level:>5} "
                f"{m['annual_return']*100:>11.2f}% {m['annual_vol']*100:>11.2f}% "
                f"{m['sharpe']:>8.2f} {m['max_drawdown']*100:>9.2f}%"
            )
        print()

    print("=" * 84)
    print("TABLE B — Hybrid routing distribution (counts across rebalances)")
    print("=" * 84)
    routing_df = pd.DataFrame(routing_log)
    if len(routing_df) > 0:
        pivot = routing_df.groupby(["risk_level", "method"]).size().unstack(fill_value=0)
        print(pivot.to_string())
    print()


if __name__ == "__main__":
    main()
