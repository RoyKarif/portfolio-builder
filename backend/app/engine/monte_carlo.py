"""Monte Carlo simulation of a portfolio's future value.

Given weights w, expected returns μ, covariance Σ, an initial value,
and a horizon — we simulate `num_paths` possible price trajectories
and summarize the distribution.

Method:
  1. Compute the *portfolio's* daily return distribution analytically.
     For weights w and asset returns r_t ~ MultivariateNormal(μ_d, Σ_d):

         r_p,t = wᵀ · r_t  ~  Normal(wᵀμ_d, wᵀΣ_d w)

     This is exact (linear combination of jointly Normal RVs is Normal).
     We sample from this 1-D distribution rather than from the full
     N-dimensional one — N times less data to generate.

  2. Sample `num_paths × num_days` daily returns.

  3. Compound: V_T = V_0 * exp(sum of daily log returns).

  4. Summarize: percentiles at each year-end (for the fan chart) and
     overall final values (for VaR and the histogram).

We store and return the random seed so the same portfolio can be
re-rendered later with the identical fan chart — full reproducibility.
"""

import numpy as np


TRADING_DAYS_PER_YEAR = 252


def simulate_portfolio(
    weights: np.ndarray,
    mu_annual: np.ndarray,
    sigma_annual: np.ndarray,
    initial_value: float,
    horizon_years: int,
    num_paths: int = 10_000,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the simulation. Returns (final_values, cumulative_log_returns).

    Args:
        weights: shape (N,), portfolio weights (sum to 1).
        mu_annual: shape (N,), annualized expected returns.
        sigma_annual: shape (N, N), annualized covariance matrix.
        initial_value: starting dollars.
        horizon_years: how many years to simulate.
        num_paths: how many independent simulations.
        seed: RNG seed for reproducibility.

    Returns:
        final_values: shape (num_paths,) — value at horizon end.
        cumulative: shape (num_paths, days) — log-return cumulatives;
                    used to extract per-year percentiles for the fan chart.
    """
    rng = np.random.default_rng(seed)
    days = horizon_years * TRADING_DAYS_PER_YEAR

    # Convert annual params to daily.
    # μ_daily = μ_annual / 252  (linearity of expectation over days)
    # σ²_daily = σ²_annual / 252  (variance scales linearly with time)
    mu_daily = mu_annual / TRADING_DAYS_PER_YEAR
    sigma_daily = sigma_annual / TRADING_DAYS_PER_YEAR

    # The portfolio's daily return distribution (Normal, by linearity).
    portfolio_mu = float(weights @ mu_daily)
    portfolio_var = float(weights @ sigma_daily @ weights)
    portfolio_sigma = float(np.sqrt(max(portfolio_var, 0.0)))

    # Sample. Shape: (num_paths, days).
    daily_returns = rng.normal(
        loc=portfolio_mu,
        scale=portfolio_sigma,
        size=(num_paths, days),
    )

    # Cumulative log-returns along each path.
    cumulative = np.cumsum(daily_returns, axis=1)

    # Final value of each path: V_0 * exp(total log return).
    final_values = initial_value * np.exp(cumulative[:, -1])

    return final_values, cumulative


def summarize(
    final_values: np.ndarray,
    cumulative: np.ndarray,
    initial_value: float,
    horizon_years: int,
) -> dict:
    """Summarize Monte Carlo results into a JSON-friendly dict.

    Includes:
      - Overall final-value percentiles: p5, p25, p50, p75, p95.
      - VaR at 5% (loss in the worst-5% scenario).
      - Year-by-year percentile timeline for the fan chart.

    The timeline lets the frontend draw a fan that opens up over time
    as uncertainty compounds.
    """
    days = cumulative.shape[1]

    # Year-end indices: year 1 ends at index 251 (0-based), year 2 at 503, etc.
    timeline = [
        # Year 0 — every path is at the initial value.
        {
            "year": 0,
            "p5": float(initial_value),
            "p25": float(initial_value),
            "p50": float(initial_value),
            "p75": float(initial_value),
            "p95": float(initial_value),
        }
    ]

    for year in range(1, horizon_years + 1):
        idx = min(year * TRADING_DAYS_PER_YEAR - 1, days - 1)
        # Values at this year-end across all paths.
        values_at_year = initial_value * np.exp(cumulative[:, idx])
        timeline.append({
            "year": year,
            "p5":  float(np.percentile(values_at_year, 5)),
            "p25": float(np.percentile(values_at_year, 25)),
            "p50": float(np.percentile(values_at_year, 50)),
            "p75": float(np.percentile(values_at_year, 75)),
            "p95": float(np.percentile(values_at_year, 95)),
        })

    p5_final = float(np.percentile(final_values, 5))

    return {
        "p5":  p5_final,
        "p25": float(np.percentile(final_values, 25)),
        "p50": float(np.percentile(final_values, 50)),
        "p75": float(np.percentile(final_values, 75)),
        "p95": float(np.percentile(final_values, 95)),
        # VaR at 5%: the loss (negative number) in the worst-5% scenario.
        "var_5": p5_final - initial_value,
        "timeline": timeline,
    }


def histogram_bins(final_values: np.ndarray, num_bins: int = 50) -> dict:
    """Pre-compute a histogram for the frontend.

    We compute it server-side instead of sending all 10,000 raw values:
      - smaller payload (~50 numbers vs 10,000)
      - frontend just renders bars

    Returns a dict with bin edges and counts.
    """
    counts, edges = np.histogram(final_values, bins=num_bins)
    return {
        "counts": counts.tolist(),
        "edges": edges.tolist(),
    }
