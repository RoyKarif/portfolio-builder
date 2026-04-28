"""Tests for the closed-form learning artifact."""

import numpy as np

from app.engine.mvo_unconstrained import tangency_portfolio


def test_tangency_weights_sum_to_one():
    mu = np.array([0.10, 0.06, 0.04])
    sigma = np.diag([0.04, 0.02, 0.01])
    w = tangency_portfolio(mu, sigma)
    assert abs(w.sum() - 1.0) < 1e-10


def test_tangency_with_zero_excess_return():
    """If μ = r_f for all assets, the formula degenerates (raw=0/0)."""
    mu = np.array([0.05, 0.05])
    sigma = np.eye(2) * 0.04
    # This will produce nan or inf — that's fine, it's a documented edge case.
    # We just verify it doesn't crash with an unrelated exception.
    w = tangency_portfolio(mu, sigma, risk_free_rate=0.05)
    assert w.shape == (2,)
