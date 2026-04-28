"""Markowitz Mean-Variance Optimization.

The central model of the project. Given:
  - μ (vector of expected returns)
  - Σ (covariance matrix)
  - σ_target (max acceptable portfolio volatility)
  - max_single_weight (per-asset cap)
  - max_class_weight (per-asset-class cap)
  - asset_classes (parallel to μ; needed for the class cap)

…find the weights vector w that maximizes expected return while
keeping portfolio risk under the limit AND respecting both
diversification caps.

Mathematical statement:

    Maximize:     μᵀw
    Subject to:   wᵀΣw ≤ σ_target²
                  sum(w) = 1
                  0 ≤ w_i ≤ max_single_weight             ∀i
                  Σ_{i∈class}  w_i ≤ max_class_weight     ∀class

Why two caps?

Without them, classic MVO is famous for producing concentrated
3-asset portfolios — it aggressively exploits even tiny differences
in historical μ. The single-asset cap forces breadth; the class cap
forces *cross-asset-class* diversification (e.g., even at risk level
5 you can't go 100% equity).

This is a Quadratic Program. We solve it with cvxpy.
"""

import cvxpy as cp
import numpy as np


# Maps the user-facing risk slider (1..5) to a target annualized
# volatility.
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
    max_single_weight: float = 0.20,
    max_class_weight: float = 0.50,
    asset_classes: list[str] | None = None,
) -> np.ndarray:
    """Solve the MVO problem and return optimal weights.

    Args:
        mu: 1-D array of length N — expected annualized returns.
        sigma: N×N positive semi-definite covariance matrix.
        target_volatility: max annualized portfolio σ (e.g. 0.12 for 12%).
        max_single_weight: per-asset cap (default 20%). Forces ≥ 5 holdings.
        max_class_weight: per-asset-class cap (default 50%). Prevents any
            single class (equity / bond / commodity / real_estate / cash)
            from dominating.
        asset_classes: list of length N giving the class of each asset
            (parallel to `mu`). If None, the class cap is skipped.

    Returns:
        1-D array of length N with non-negative weights summing to 1.

    Raises:
        ValueError if the solver fails to find an optimal solution.
    """
    n = len(mu)
    w = cp.Variable(n)
    objective = cp.Maximize(mu @ w)

    constraints = [
        cp.sum(w) == 1,
        w >= 0,
        w <= max_single_weight,
        cp.quad_form(w, sigma) <= target_volatility ** 2,
    ]

    # Per-class cap. For each unique class, the sum of weights of
    # assets in that class must be ≤ max_class_weight.
    if asset_classes is not None:
        if len(asset_classes) != n:
            raise ValueError(
                f"asset_classes length {len(asset_classes)} != mu length {n}"
            )
        for cls in set(asset_classes):
            # Indicator vector: 1 where asset is in this class, 0 otherwise.
            mask = np.array(
                [1.0 if c == cls else 0.0 for c in asset_classes]
            )
            constraints.append(mask @ w <= max_class_weight)

    problem = cp.Problem(objective, constraints)
    problem.solve()

    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise ValueError(
            f"MVO failed: status={problem.status}. "
            f"Try a higher target_volatility or relax the class cap."
        )

    # Clamp negatives that arise from solver tolerance (e.g. -1e-12).
    weights = np.array(w.value).flatten()
    weights[weights < 0] = 0.0

    # Renormalize so they sum to exactly 1 (clamping introduces tiny drift).
    total = weights.sum()
    if total > 0:
        weights = weights / total

    return weights
