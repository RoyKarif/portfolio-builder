import hashlib
import json

import numpy as np


def _deterministic_seed(
    weights,
    expected_returns,
    cov_matrix,
    initial_value: float,
    horizon_years: float,
    n_simulations: int,
) -> int:
    """Derive a 32-bit seed from the simulator's actual inputs.

    Assumes weights, expected_returns, and cov_matrix are aligned to a
    single, deterministically ordered ticker set. The pipeline guarantees
    this via its post-estimate_covariance realignment step
    (see covariance-shrinkage Task 4).
    """
    payload = json.dumps(
        {
            "weights":          [round(float(w), 6) for w in weights],
            "expected_returns": [round(float(r), 6) for r in expected_returns],
            "cov_matrix":       [[round(float(c), 8) for c in row] for row in cov_matrix],
            "initial_value":    round(float(initial_value), 4),
            "horizon_years":    round(float(horizon_years), 4),
            "n_simulations":    int(n_simulations),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:4], "big")


def run_monte_carlo(
    weights: np.ndarray,
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    initial_value: float,
    horizon_years: float,
    n_simulations: int = 10_000,
) -> dict:
    trading_days = int(252 * horizon_years)
    port_annual_return = float(weights @ expected_returns)
    port_annual_vol = float(np.sqrt(weights @ cov_matrix @ weights))
    daily_return = port_annual_return / 252
    daily_vol = port_annual_vol / np.sqrt(252)

    seed = _deterministic_seed(
        weights, expected_returns, cov_matrix,
        initial_value, horizon_years, n_simulations,
    )
    rng = np.random.default_rng(seed=seed)
    random_returns = rng.normal(daily_return, daily_vol, (n_simulations, trading_days))
    cumulative = np.cumprod(1 + random_returns, axis=1)
    final_values = initial_value * cumulative[:, -1]

    p10 = float(np.percentile(final_values, 10))
    p50 = float(np.percentile(final_values, 50))
    p90 = float(np.percentile(final_values, 90))

    return_low = (p10 / initial_value) ** (1 / horizon_years) - 1
    return_high = (p90 / initial_value) ** (1 / horizon_years) - 1

    return {
        "percentile_10": round(p10, 2),
        "percentile_50": round(p50, 2),
        "percentile_90": round(p90, 2),
        "return_low": round(return_low, 4),
        "return_high": round(return_high, 4),
        "initial_value": initial_value,
        "horizon_years": horizon_years,
        "n_simulations": n_simulations,
    }
