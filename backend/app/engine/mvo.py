"""Markowitz Mean-Variance Optimization.

The central model of the project. Given:
  - μ (vector of expected returns)
  - Σ (covariance matrix)
  - σ_target (max acceptable portfolio volatility)
  - max_single_weight (per-asset cap)
  - class_caps (per-asset-class caps)
  - asset_classes (parallel to μ; needed for the class caps)

…find the weights vector w that maximizes expected return while
keeping portfolio risk under the limit AND respecting both
diversification caps.

Mathematical statement:

    Maximize:     μᵀw
    Subject to:   wᵀΣw ≤ σ_target²
                  sum(w) = 1
                  0 ≤ w_i ≤ max_single_weight             ∀i
                  Σ_{i∈class}  w_i ≤ class_caps[class]    ∀class

Why two layers of caps?

Without them, classic MVO is famous for producing concentrated
3-asset portfolios — it aggressively exploits even tiny differences
in historical μ. The single-asset cap forces breadth; the class cap
forces *cross-asset-class* diversification.

Why class caps are NOT uniform:
  - "Risky" classes (equity, commodity, real_estate) get capped to
    prevent over-concentration in volatile assets.
  - "Safe" classes (bond, cash) get NO cap. At low risk levels, the
    only feasible portfolios are dominated by bonds/cash; capping
    them would make e.g. risk level 1 (5% vol target) infeasible.

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


# Default per-class caps. Risky asset classes are capped to prevent
# over-concentration; safe classes (bond, cash) are unconstrained so
# that low-risk portfolios remain feasible.
DEFAULT_CLASS_CAPS: dict[str, float] = {
    "equity":      0.70,  # max 70% equity → at high risk forces some non-equity
    "commodity":   0.30,  # commodities are speculative, cap them
    "real_estate": 0.30,
    "bond":        1.00,  # no cap (allows 100% bonds for risk level 1)
    "cash":        1.00,  # no cap
}


def solve_mvo(
    mu: np.ndarray,
    sigma: np.ndarray,
    target_volatility: float,
    max_single_weight: float = 0.20,
    asset_classes: list[str] | None = None,
    class_caps: dict[str, float] | None = None,
) -> np.ndarray:
    """Solve the MVO problem and return optimal weights.

    Args:
        mu: 1-D array of length N — expected annualized returns.
        sigma: N×N positive semi-definite covariance matrix.
        target_volatility: max annualized portfolio σ (e.g. 0.12 for 12%).
        max_single_weight: per-asset cap (default 20%). Forces ≥ 5 holdings.
        asset_classes: list of length N giving the class of each asset
            (parallel to `mu`). If None, no class cap is applied.
        class_caps: dict mapping class name → max weight in that class.
            Defaults to DEFAULT_CLASS_CAPS. Classes not present in the
            dict are unconstrained.

    Returns:
        1-D array of length N with non-negative weights summing to 1.

    Raises:
        ValueError if the solver fails (typically infeasible — try a
        looser caps or higher target volatility).
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

    # Per-class caps. Classes not in `class_caps` (or with cap >= 1.0)
    # get no constraint.
    #
    # IMPORTANT: a class cap can become infeasible if the universe doesn't
    # have enough OTHER-class assets to fill (1 - cap). For example, if
    # the user filtered to "stocks only", the universe is 100% equity,
    # and an equity cap of 70% requires 30% in non-equity → impossible.
    # We auto-relax any cap that conflicts with the universe composition.
    if asset_classes is not None:
        if len(asset_classes) != n:
            raise ValueError(
                f"asset_classes length {len(asset_classes)} != mu length {n}"
            )
        caps = class_caps if class_caps is not None else DEFAULT_CLASS_CAPS
        for cls in set(asset_classes):
            cap = caps.get(cls, 1.0)
            if cap >= 1.0:
                continue

            # Maximum possible allocation to assets NOT in this class,
            # given the per-asset cap. (This ignores the per-class caps
            # on the *other* classes, which is a conservative upper
            # bound — good enough for feasibility detection.)
            n_other = sum(1 for c in asset_classes if c != cls)
            max_other_alloc = n_other * max_single_weight

            # The class cap requires (1 - cap) to live in other classes.
            # If max_other_alloc can't supply that, raise the cap.
            required_other = 1.0 - cap
            if max_other_alloc < required_other - 1e-9:
                cap = 1.0 - max_other_alloc  # the most we can demand of "other"

            if cap >= 1.0 - 1e-9:
                continue  # would be a no-op constraint

            mask = np.array(
                [1.0 if c == cls else 0.0 for c in asset_classes]
            )
            constraints.append(mask @ w <= cap)

    problem = cp.Problem(objective, constraints)
    problem.solve()

    if problem.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise ValueError(
            f"MVO failed: status={problem.status}. "
            f"Try a different risk level or include more asset classes."
        )

    weights = np.array(w.value).flatten()
    weights[weights < 0] = 0.0
    total = weights.sum()
    if total > 0:
        weights = weights / total
    return weights
