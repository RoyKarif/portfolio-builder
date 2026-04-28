"""Synthetic price generator — fallback for when yfinance is broken.

Generates 10 years of realistic-looking daily prices using Geometric
Brownian Motion (GBM):

    P_t = P_{t-1} * exp(r_t)
    r_t ~ Normal(μ_daily, σ_daily)

with μ and σ chosen per asset class to match real-world averages:
- equity ~10% return, ~16% volatility
- bond   ~3%  return, ~5%  volatility
- commodity ~4% return, ~18% volatility
- real_estate ~7% return, ~17% volatility
- cash   ~1.5% return, ~0.5% volatility

These are NOT real prices. They're statistically realistic enough that
MVO + Monte Carlo produce sensible-looking portfolios for a demo, but
do NOT use this for actual investment decisions.

Why this exists: yfinance breaks every few months as Yahoo changes
their API. Falling back to synthetic data means the demo always works,
and the math is exactly the same — only the inputs are simulated.
"""

from __future__ import annotations
from datetime import date, timedelta

import numpy as np


# Realistic annualized (μ, σ) per asset class, chosen by looking at
# long-run averages of US ETFs.
ASSET_CLASS_PARAMS: dict[str, tuple[float, float]] = {
    "equity":      (0.10, 0.16),
    "bond":        (0.03, 0.05),
    "commodity":   (0.04, 0.18),
    "real_estate": (0.07, 0.17),
    "cash":        (0.015, 0.005),
}


def synthetic_price_history(
    ticker: str,
    asset_class: str,
    years: int = 10,
    seed: int | None = None,
) -> list[tuple[date, float]]:
    """Return a synthetic 10y price history list for one asset.

    The seed is deterministic per ticker (hash of the ticker string),
    so re-running the seed script produces identical prices.
    """
    mu_annual, sigma_annual = ASSET_CLASS_PARAMS.get(
        asset_class, ASSET_CLASS_PARAMS["equity"]  # fallback
    )

    # Per-asset deterministic seed — identical re-runs produce identical data.
    if seed is None:
        seed = abs(hash(ticker)) % (2**32)
    rng = np.random.default_rng(seed)

    days = years * 252
    mu_daily = mu_annual / 252
    sigma_daily = sigma_annual / np.sqrt(252)

    daily_returns = rng.normal(mu_daily, sigma_daily, days)

    # Start at $100; compound.
    prices = 100.0 * np.exp(np.cumsum(daily_returns))

    # Generate calendar of *trading* days going backward from today.
    # We include only weekdays (Mon-Fri) to mimic real markets.
    rows: list[tuple[date, float]] = []
    d = date.today()
    while len(rows) < days:
        if d.weekday() < 5:  # Mon=0 ... Fri=4
            rows.append((d, float(prices[len(prices) - 1 - len(rows)])))
        d -= timedelta(days=1)

    rows.reverse()  # oldest first
    return rows
