"""Markowitz Mean-Variance Optimization.

The central model of the project. Given:
  - μ (vector of expected returns)
  - Σ (covariance matrix)
  - σ_target (max acceptable portfolio volatility)
  - max_single_weight (diversification constraint)

…find the weights vector w that maximizes expected return while
keeping portfolio risk under the limit.

Mathematical statement:

    Maximize:     μᵀw                         (expected portfolio return)
    Subject to:   wᵀΣw ≤ σ_target²            (variance under limit)
                  sum(w) = 1                   (fully invested)
                  0 ≤ w_i ≤ max_single_weight (long-only, diversified)

This is a Quadratic Program (linear objective, quadratic constraint).
We solve it with cvxpy, which converts the problem to conic form and
hands it to an interior-point solver.

Note: the constraint is `wᵀΣw ≤ σ²` (not `√(wᵀΣw) ≤ σ`) because both
sides are non-negative — squaring is equivalent and produces a cleaner
QP.
"""

import cvxpy as cp
import numpy as np


# Maps the user-facing risk slider (1..5) to a target annualized
# volatility. These values are chosen to span the practical range:
#   1 = ~5%  (mostly bonds, very conservative)
#   3 = ~12% (balanced)
#   5 = ~20% (close to all-equity, ~SPY volatility)
RISK_LEVEL_TO_VOLATILITY: dict[int, float] = {
    1: 0.05,
    2: 0.08,
    3: 0.12,
    4: 0.16,
    5: 0.20,
}


def solve_mvo(
    mu: np.ndarray,
    sigma: np.ndarray,
    target_volatility: float,
    max_single_weight: float = 0.4,
) -> np.ndarray:
    """Solve the MVO problem and return optimal weights.

    Args:
        mu: 1-D array of length N — expected annualized returns.
        sigma: N×N positive semi-definite covariance matrix.
        target_volatility: max annualized portfolio σ (e.g. 0.12 for 12%).
        max_single_weight: hard cap per asset (default 0.4 = 40%).
            Without this, MVO often piles into the highest-μ asset alone;
            this constraint forces diversification.

    Returns:
        1-D array of length N with non-negative weights summing to 1.

    Raises:
        ValueError if the solver fails to find an optimal solution
        (typically means the problem is infeasible — e.g. target_volatility
        smaller than the minimum-variance portfolio's σ).
    """
    n = len(mu)

    # Decision variable: the weights vector.
    w = cp.Variable(n)

    # Objective: maximize linear function of w.
    # `mu @ w` is the dot product — cvxpy's @ is overloaded.
    objective = cp.Maximize(mu @ w)

    # Constraints — each one becomes a row in the conic form.
    constraints = [
        # Fully invested.
        cp.sum(w) == 1,
        # Long-only.
        w >= 0,
        # Per-asset cap (diversification).
        w <= max_single_weight,
        # Variance under target². cvxpy.quad_form is wᵀΣw, and it
        # automatically verifies that Σ is positive semi-definite.
        cp.quad_form(w, sigma) <= target_volatility ** 2,
    ]

    problem = cp.Problem(objective, constraints)
    problem.solve()

    # Cvxpy returns one of: OPTIMAL, OPTIMAL_INACCURATE, INFEASIBLE,
    # UNBOUNDED, etc. We accept the first two (INACCURATE just means
    # solver tolerance was loose, but the answer is still good).
    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise ValueError(
            f"MVO failed: status={problem.status}. "
            f"Try a higher target_volatility."
        )

    # Clamp negatives that arise from solver tolerance (e.g. -1e-12).
    weights = np.array(w.value).flatten()
    weights[weights < 0] = 0.0

    # Renormalize so they sum to exactly 1 (clamping introduces tiny drift).
    total = weights.sum()
    if total > 0:
        weights = weights / total

    return weights
