"""Closed-form solution to the unconstrained MVO problem.

This is a *learning artifact*. It's not used in production (the
constrained version in `mvo.py` is). We keep it because:

  1. Deriving and implementing the closed form proves real understanding
     of the math — useful in interviews ("can you derive MVO from
     Lagrange multipliers?").
  2. It's a sanity check: in the limit where constraints are inactive,
     the constrained solver should agree with the closed-form answer.

The unconstrained problem:

    Maximize:    μᵀw
    Subject to:  sum(w) = 1                (no σ-target, no w≥0)

Using a Lagrange multiplier λ for the budget constraint:

    L(w, λ) = μᵀw - λ(1ᵀw - 1)

Setting ∂L/∂w = 0 gives μ = λ·1, which is degenerate (objective is
linear). To make this a meaningful problem we add a quadratic penalty:

    Maximize:    μᵀw - (γ/2)·wᵀΣw
    Subject to:  sum(w) = 1

For γ > 0 this has a unique closed-form solution:

    w* = (1/γ) * Σ⁻¹ * μ + adjustment_to_satisfy_budget

The "tangency portfolio" (commonly cited) is the special case where we
maximize Sharpe ratio (μ - r_f)ᵀw / sqrt(wᵀΣw) and the answer is:

    w* = Σ⁻¹ (μ - r_f·1) / (1ᵀ Σ⁻¹ (μ - r_f·1))

This file implements the tangency portfolio version.
"""

import numpy as np


def tangency_portfolio(
    mu: np.ndarray,
    sigma: np.ndarray,
    risk_free_rate: float = 0.0,
) -> np.ndarray:
    """Closed-form maximum-Sharpe portfolio (no constraints other than sum=1).

    Formula:
        w* = Σ⁻¹ (μ - r_f·1) / (1ᵀ Σ⁻¹ (μ - r_f·1))

    May produce negative weights (shorts) — that's fine for a sanity
    check, but unsuitable for a real long-only investor.

    Returns: 1-D array of length N.
    """
    n = len(mu)
    excess = mu - risk_free_rate * np.ones(n)
    sigma_inv = np.linalg.inv(sigma)
    raw = sigma_inv @ excess
    return raw / raw.sum()
