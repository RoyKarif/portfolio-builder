"""Tests for engine.mvo — the core optimizer."""

import numpy as np
import pytest

from app.engine.mvo import solve_mvo, RISK_LEVEL_TO_VOLATILITY


# Tests that exercise the *math* on tiny (3-asset) universes pass
# max_single_weight=1.0 explicitly. The default per-asset cap (0.20) plus
# sum(w)=1 requires at least 5 assets to be feasible — that diversification
# behavior is covered separately by test_mvo_diversification_constraint_enforced.
def test_mvo_weights_sum_to_one():
    mu = np.array([0.10, 0.06, 0.04])
    sigma = np.diag([0.04, 0.02, 0.01])  # uncorrelated
    w = solve_mvo(mu, sigma, target_volatility=0.15, max_single_weight=1.0)
    assert abs(w.sum() - 1.0) < 1e-6


def test_mvo_long_only():
    """No negative weights."""
    mu = np.array([0.10, 0.06, 0.04])
    sigma = np.diag([0.04, 0.02, 0.01])
    w = solve_mvo(mu, sigma, target_volatility=0.15, max_single_weight=1.0)
    assert (w >= -1e-9).all()


def test_mvo_diversification_constraint_enforced():
    """No weight exceeds max_single_weight."""
    # An asset with much higher μ — without the cap, MVO would put 100% there.
    mu = np.array([0.30, 0.05, 0.05])
    sigma = np.diag([0.04, 0.04, 0.04])
    w = solve_mvo(mu, sigma, target_volatility=0.20, max_single_weight=0.4)
    assert w.max() <= 0.4 + 1e-6


def test_mvo_target_volatility_respected():
    """Portfolio volatility ≤ target."""
    mu = np.array([0.10, 0.06, 0.04])
    sigma = np.array([
        [0.04, 0.01, 0.00],
        [0.01, 0.02, 0.00],
        [0.00, 0.00, 0.01],
    ])
    target = 0.12
    w = solve_mvo(mu, sigma, target_volatility=target, max_single_weight=1.0)
    portfolio_vol = float(np.sqrt(w @ sigma @ w))
    assert portfolio_vol <= target + 1e-3


def test_mvo_prefers_higher_return_at_same_risk():
    """Two assets, same risk — optimizer prefers the higher μ one."""
    mu = np.array([0.10, 0.05])
    sigma = np.diag([0.04, 0.04])
    w = solve_mvo(mu, sigma, target_volatility=0.20, max_single_weight=1.0)
    assert w[0] > w[1]


def test_mvo_infeasible_raises():
    """Volatility target so low that no portfolio can satisfy it."""
    mu = np.array([0.10, 0.06])
    sigma = np.diag([0.04, 0.04])
    # All long-only portfolios have σ ≥ 0.20 (= sqrt(0.04)), so 0.01 is infeasible.
    with pytest.raises(ValueError):
        solve_mvo(mu, sigma, target_volatility=0.01)


def test_risk_level_mapping_is_monotonic():
    """Higher risk level → higher target volatility."""
    levels = sorted(RISK_LEVEL_TO_VOLATILITY.keys())
    vols = [RISK_LEVEL_TO_VOLATILITY[l] for l in levels]
    assert vols == sorted(vols)
