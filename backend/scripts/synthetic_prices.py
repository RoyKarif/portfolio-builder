"""Synthetic price generator — fallback for when yfinance is broken.

Uses a single-factor model so cross-asset correlations are realistic.

Model (per ticker, per day):

    r_t = β_class × market_t + ε_t(ticker) + idio_drift_daily

where:
  - market_t is a SHARED daily return series, identical across all
    tickers (generated with a fixed seed). It represents a hypothetical
    "global market" with μ=10%, σ=14%.
  - ε_t is per-ticker idiosyncratic noise (uncorrelated across tickers).
  - β_class and idio_drift, σ_idio are picked per asset class so that
    total per-class (μ, σ) match historical averages AND inter-class
    correlations look like reality:

       equity-equity      ≈ +0.75
       bond-bond          ≈ +0.10
       equity-bond        ≈ -0.30   (bonds hedge equity)
       equity-commodity   ≈ +0.25
       equity-real_estate ≈ +0.60   (REITs co-move with equity)
       cash-anything      ≈  0

Why a factor model (and not just one shared series):
  - A single shared series with no idio would give correlation = 1 within
    a class — too strong. The idio component breaks perfect correlation.
  - Independent draws per ticker (the previous bug) gave correlation ≈ 0
    inside-class — way too weak. Portfolio vol came out 4x too low,
    inflating Sharpe to ~2.7.

Why these specific numbers:
  - Market σ = 14% (a bit lower than equity vol). Equity vol comes from
    market exposure (β=1, contributing 14%) + idio (0.08), giving
    total ≈ 16% — matches realistic broad-equity ETF vol.
  - Bond β = -0.10 generates the negative equity-bond correlation that
    appeared in the post-2000 macro regime. (In the 1970s it was positive;
    we go with the modern regime since the spec assumes recent data.)
  - Real-estate β = 0.70 captures REITs' high correlation to equity
    while still being distinguishable.

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


# Shared market factor (annualized).
MARKET_MU: float = 0.10
MARKET_SIGMA: float = 0.14

# Fixed seed for the market factor — every call to this module on a
# given day must see the SAME market series. That shared series is what
# induces correlations between assets.
_MARKET_SEED: int = 19770808  # arbitrary fixed integer


# Per-asset-class factor params:  (beta_to_market, idio_drift, idio_sigma).
# All values are annualized.
#
# Total-vol formula (annual):  σ_total = √( (β·σ_M)² + σ_idio² )
# Total-drift formula (annual): μ_total = β·μ_M + idio_drift
ASSET_CLASS_FACTORS: dict[str, tuple[float, float, float]] = {
    "equity":      (1.00,  0.00,   0.08),  # ⇒ μ=10.0%,  σ≈16.1%
    "bond":        (-0.10, 0.04,   0.04),  # ⇒ μ= 3.0%,  σ≈ 4.2%
    "commodity":   (0.30,  0.01,   0.16),  # ⇒ μ= 4.0%,  σ≈16.5%
    "real_estate": (0.70,  0.00,   0.10),  # ⇒ μ= 7.0%,  σ≈14.0%
    "cash":        (0.00,  0.015,  0.005), # ⇒ μ= 1.5%,  σ≈ 0.5%
}


def _market_factor_series(days: int) -> np.ndarray:
    """Generate the shared daily market-factor return series.

    Uses a fixed seed so every ticker fetched in the same session sees
    the SAME market path. That's the mechanism that creates correlations
    between assets.
    """
    rng = np.random.default_rng(_MARKET_SEED)
    return rng.normal(
        MARKET_MU / 252,
        MARKET_SIGMA / np.sqrt(252),
        days,
    )


def synthetic_price_history(
    ticker: str,
    asset_class: str,
    years: int = 10,
    seed: int | None = None,
) -> list[tuple[date, float]]:
    """Return a synthetic 10y price history list for one asset.

    Daily return is a linear combination of the shared market factor
    plus per-ticker idiosyncratic noise:
        r_t = β·m_t + ε_t + idio_drift/252

    The ticker's seed only affects ε_t (uncorrelated noise), so two
    tickers in the same class share their market component but differ
    in their idiosyncratic component — yielding inter-asset correlation
    < 1 but > 0, like real markets.

    The seed is deterministic per ticker (hash of the ticker string),
    so re-running this function produces identical prices.
    """
    if asset_class not in ASSET_CLASS_FACTORS:
        # Unknown class → treat as equity (most common case for custom tickers).
        asset_class = "equity"
    beta, idio_drift_annual, idio_sigma_annual = ASSET_CLASS_FACTORS[asset_class]

    # Per-ticker deterministic seed for the idiosyncratic component only.
    if seed is None:
        seed = abs(hash(ticker)) % (2**32)
    rng = np.random.default_rng(seed)

    days = years * 252

    # Shared component: the same market path every call.
    market = _market_factor_series(days)

    # Idiosyncratic component: independent per ticker.
    idio = rng.normal(
        idio_drift_annual / 252,
        idio_sigma_annual / np.sqrt(252),
        days,
    )

    daily_returns = beta * market + idio

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
