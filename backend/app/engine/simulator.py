import numpy as np


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

    np.random.seed(None)
    random_returns = np.random.normal(daily_return, daily_vol, (n_simulations, trading_days))
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
