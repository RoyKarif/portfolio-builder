import numpy as np
import cvxpy as cp

RISK_VOLATILITY_CAP = {
    1: 0.08,
    2: 0.12,
    3: 0.18,
    4: 0.25,
    5: 0.35,
}

# Caveat: when the screened universe is exactly 5 tickers, the constraints
# sum(w) == 1 and w_i <= 0.20 jointly force every w_i = 0.20, regardless of
# risk_level or expected returns. The optimizer becomes a no-op equal-weight
# allocator on that boundary. This is an accepted consequence of using the
# weight cap as the de facto MIN_STOCKS enforcement; raising the upstream
# >=5 ticker guard would change behavior for users with narrow universes.
MAX_SINGLE_WEIGHT = 0.20

# Enforced indirectly via MAX_SINGLE_WEIGHT: any feasible solution must
# spread across at least 1 / MAX_SINGLE_WEIGHT = 5 names. CVXPY does not
# support the cardinality constraint that would express this directly.
MIN_STOCKS = 5

MIN_WEIGHT_THRESHOLD = 0.02


def optimize_portfolio(
    tickers: list[str],
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_level: int,
) -> dict:
    n = len(tickers)
    max_vol = RISK_VOLATILITY_CAP.get(risk_level, 0.18)

    weights = cp.Variable(n)
    ret = expected_returns @ weights
    risk = cp.quad_form(weights, cov_matrix)

    constraints = [
        cp.sum(weights) == 1,
        weights >= 0,
        weights <= MAX_SINGLE_WEIGHT,
    ]
    constraints.append(risk <= max_vol ** 2)

    objective = cp.Maximize(ret)
    problem = cp.Problem(objective, constraints)

    try:
        problem.solve(solver=cp.SCS)
    except cp.SolverError:
        problem.solve(solver=cp.ECOS)

    if problem.status not in ("optimal", "optimal_inaccurate"):
        equal_w = np.ones(n) / n
        return {
            "weights": {t: round(float(w), 4) for t, w in zip(tickers, equal_w)},
            "portfolio_return": float(expected_returns @ equal_w),
            "portfolio_volatility": float(np.sqrt(equal_w @ cov_matrix @ equal_w)),
            "status": "fallback_equal_weight",
        }

    raw_weights = weights.value
    clean_weights = np.where(raw_weights < MIN_WEIGHT_THRESHOLD, 0, raw_weights)
    if clean_weights.sum() > 0:
        clean_weights = clean_weights / clean_weights.sum()
    else:
        clean_weights = np.ones(n) / n

    port_return = float(expected_returns @ clean_weights)
    port_vol = float(np.sqrt(clean_weights @ cov_matrix @ clean_weights))

    return {
        "weights": {t: round(float(w), 4) for t, w in zip(tickers, clean_weights)},
        "portfolio_return": round(port_return, 4),
        "portfolio_volatility": round(port_vol, 4),
        "status": "optimal",
    }
