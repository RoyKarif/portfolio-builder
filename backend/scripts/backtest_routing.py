"""Walk-forward backtest of HRP / MVO / hybrid / equal-weight on realized returns.

Quarterly rebalancing on a 35-ticker multi-sector universe (top US tech,
healthcare, energy, finance, consumer, industrial + 5 defensive ETFs)
across two distinct 4-year windows (2016-2019 and 2021-2024). Compares
4 strategies at 3 risk levels.

For each rebalance: fit cov + μ on the trailing 2-year window, run each
strategy to produce weights, hold those weights until the next rebalance.
Each strategy's daily return stream is the concatenation of (held weights
× asset returns) over the entire window. Metrics are computed on the
continuous stream.

Strategies (per risk level 1, 3, 5):
- equal_weight: 1/N baseline (independent of risk_level)
- hrp_only:    pure HRP, no MVO fallback (independent of risk_level)
- mvo_only:    pure MVO at the given risk_level cap
- hybrid:      full P5 routing logic (HRP within band, MVO outside)

Metrics per (strategy, risk_level), reported per window AND combined:
- Annualized return (geometric)
- Annualized vol (realized)
- Sharpe (rf = 0)
- Max drawdown
- For hybrid: routing distribution across rebalances (combined)

Caveats (deliberately accepted for v1 of the rich backtest):
- Sample-mean expected returns for MVO. Production XGBoost predictor
  walk-forward retraining is the next phase. Sample mean isolates the
  universe / cadence / regime variables from the μ-source variable.
- No transaction costs (quarterly rebalance has more friction than
  P6's annual but still small relative to absolute returns).
- Fixed universe; no point-in-time membership adjustment (survivorship
  bias toward currently-known names).
- 2020 deliberately excluded from both windows (anomalous COVID crash
  + recovery in a single year).

Usage:
    cd backend && python scripts/backtest_routing.py
"""
import sys
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


# 35 tickers across 6 sectors + 5 defensive ETFs.
# Curated for liquidity and history back to 2014.
UNIVERSE = [
    # Tech (5)
    "MSFT", "AAPL", "NVDA", "GOOGL", "AMZN",
    # Healthcare (5)
    "JNJ", "UNH", "LLY", "MRK", "PFE",
    # Energy (5)
    "XOM", "CVX", "COP", "SLB", "OXY",
    # Finance (5)
    "JPM", "BAC", "WFC", "GS", "BLK",
    # Consumer (5)
    "HD", "NKE", "MCD", "SBUX", "LOW",
    # Industrial (5)
    "BA", "CAT", "HON", "UPS", "RTX",
    # Defensive ETFs (5) — per P4
    "AGG", "IEF", "GLD", "XLU", "XLP",
]

# Two 4-year evaluation windows (16 quarterly rebalances each).
# 2-year trailing window used for fitting at each rebalance, so data
# fetch needs to start 2 years before the earliest window.
WINDOWS = [
    ("2016-01-01", "2019-12-31"),  # pre-pandemic
    ("2021-01-01", "2024-12-31"),  # post-COVID + 2022 drawdown
]
DATA_FETCH_START = "2014-01-01"
DATA_FETCH_END = "2024-12-31"

RISK_LEVELS = [1, 3, 5]
TRAINING_WINDOW_YEARS = 2
TRADING_DAYS = 252


def fetch_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Returns DataFrame of close prices indexed by date, columns=tickers.
    Drops any ticker without ≥95% coverage over the window."""
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
    if df.empty:
        return df
    n_max = df.notna().sum().max()
    coverage = df.notna().sum() / n_max
    keep = coverage[coverage >= 0.95].index
    df = df[keep].dropna()
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


def run_strategies(returns_train: pd.DataFrame, risk_level: int) -> dict | None:
    """Compute weights for all 4 strategies at this rebalance. Returns
    None if the universe at this point is too small to backtest."""
    try:
        cov, _, cov_meta = estimate_covariance(returns_train)
    except Exception:
        return None
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


def metrics(daily_returns: pd.Series) -> dict | None:
    """Annualized return / vol / Sharpe / max drawdown from daily series."""
    if daily_returns is None or len(daily_returns) == 0:
        return None
    n_days = len(daily_returns)
    annual_return = float((1 + daily_returns).prod() ** (TRADING_DAYS / n_days) - 1)
    annual_vol = float(daily_returns.std() * np.sqrt(TRADING_DAYS))
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0.0
    cumulative = (1 + daily_returns).cumprod()
    drawdown = (cumulative - cumulative.cummax()) / cumulative.cummax()
    return {
        "annual_return": annual_return,
        "annual_vol": annual_vol,
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
    }


def run_window(prices: pd.DataFrame, window_start: str, window_end: str) -> tuple[dict, list]:
    """Walk-forward backtest over a single window. Returns:
      - results: {(strategy, risk_level): pd.Series of daily returns spanning the window}
      - routing_log: list of {risk_level, date, method} dicts for the hybrid strategy
    """
    win_start_ts = pd.Timestamp(window_start)
    win_end_ts = pd.Timestamp(window_end)
    in_window = prices.loc[win_start_ts:win_end_ts]
    if in_window.empty:
        return {}, []

    # Quarterly rebalance dates: first trading day on/after each quarter start.
    rebalance_dates = []
    cursor = win_start_ts
    while cursor <= win_end_ts:
        idx = prices.index.searchsorted(cursor)
        if idx < len(prices.index) and prices.index[idx] <= win_end_ts:
            rebalance_dates.append(prices.index[idx])
        cursor = cursor + pd.DateOffset(months=3)

    results: dict = {}
    routing_log: list = []

    for risk_level in RISK_LEVELS:
        # Per-strategy daily-return stream accumulator
        per_strategy_returns: dict[str, list[pd.Series]] = {
            "equal_weight": [], "hrp_only": [], "mvo_only": [], "hybrid": [],
        }

        for i, rebal_date in enumerate(rebalance_dates):
            train_start = rebal_date - pd.DateOffset(years=TRAINING_WINDOW_YEARS)
            prices_train = prices.loc[train_start:rebal_date]
            returns_train = prices_train.pct_change().dropna()
            if len(returns_train) < 100:
                continue

            strats = run_strategies(returns_train, risk_level)
            if strats is None:
                continue

            # Hold weights from this rebalance until the next one (or window end)
            if i + 1 < len(rebalance_dates):
                hold_end = rebalance_dates[i + 1]
            else:
                hold_end = win_end_ts
            prices_hold = prices.loc[rebal_date:hold_end][strats["tickers"]]
            asset_returns = prices_hold.pct_change().dropna()
            if asset_returns.empty:
                continue

            for strat in ["equal_weight", "hrp_only", "mvo_only", "hybrid"]:
                weights = strats[strat]
                if weights is None:
                    continue
                portfolio_returns = asset_returns @ weights
                per_strategy_returns[strat].append(portfolio_returns)

            if risk_level == RISK_LEVELS[0]:
                # Routing log is risk-level-specific; capture for all 3 levels
                pass
            routing_log.append({
                "risk_level": risk_level,
                "date": rebal_date.date(),
                "method": strats["hybrid_method"],
            })

        for strat, series_list in per_strategy_returns.items():
            if series_list:
                results[(strat, risk_level)] = pd.concat(series_list)

    return results, routing_log


def print_window(label: str, results: dict):
    print("=" * 84)
    print(f"TABLE A — {label}")
    print("=" * 84)
    print(f"{'strategy':<15} {'risk':>5} {'annual_ret':>12} {'annual_vol':>12} {'sharpe':>8} {'max_dd':>10}")
    print("-" * 84)
    for risk_level in RISK_LEVELS:
        for strat in ["equal_weight", "hrp_only", "mvo_only", "hybrid"]:
            key = (strat, risk_level)
            if key not in results:
                print(f"{strat:<15} {risk_level:>5}     (no data)")
                continue
            m = metrics(results[key])
            print(
                f"{strat:<15} {risk_level:>5} "
                f"{m['annual_return']*100:>11.2f}% {m['annual_vol']*100:>11.2f}% "
                f"{m['sharpe']:>8.2f} {m['max_drawdown']*100:>9.2f}%"
            )
        print()


def main():
    print(f"Fetching prices for {len(UNIVERSE)} tickers ({DATA_FETCH_START} to {DATA_FETCH_END})...")
    prices = fetch_prices(UNIVERSE, DATA_FETCH_START, DATA_FETCH_END)
    if prices.empty:
        print("ERROR: no price data fetched")
        return
    print(f"Got {len(prices)} trading days, {len(prices.columns)} tickers retained: "
          f"{sorted(prices.columns)}")
    print()

    all_window_results = []
    all_routing_logs = []

    for window_start, window_end in WINDOWS:
        print(f"Running window {window_start} to {window_end}...")
        results, routing_log = run_window(prices, window_start, window_end)
        all_window_results.append((f"Window {window_start[:4]}-{window_end[:4]}", results))
        all_routing_logs.extend(routing_log)
        print()

    for label, results in all_window_results:
        print_window(label, results)

    # Combined-windows view: concatenate the two windows' return series per (strat, risk)
    combined = {}
    for label, results in all_window_results:
        for key, series in results.items():
            combined.setdefault(key, []).append(series)
    combined = {k: pd.concat(v) for k, v in combined.items()}
    print_window("Combined (both windows)", combined)

    print("=" * 84)
    print("TABLE B — Hybrid routing distribution (counts across all rebalances, both windows)")
    print("=" * 84)
    routing_df = pd.DataFrame(all_routing_logs)
    if len(routing_df) > 0:
        pivot = routing_df.groupby(["risk_level", "method"]).size().unstack(fill_value=0)
        print(pivot.to_string())
    print()


if __name__ == "__main__":
    main()
