"""Tests for engine.statistics."""

import numpy as np
import pandas as pd

from app.engine.statistics import mean_returns, covariance_matrix


def test_mean_returns_annualized():
    """Daily mean × 252 = annualized mean."""
    daily = pd.DataFrame({
        "X": [0.001] * 252,  # constant 0.1% per day
    })
    result = mean_returns(daily)
    np.testing.assert_allclose(result, [0.252], rtol=1e-10)


def test_covariance_matrix_diagonal_is_variance():
    """Σ[i,i] should equal annualized variance of asset i."""
    rng = np.random.default_rng(0)
    n_days = 1000
    daily = pd.DataFrame({
        "X": rng.normal(0, 0.01, n_days),  # σ_daily = 0.01
    })
    sigma = covariance_matrix(daily)

    # Annualized variance ≈ 0.01² × 252 = 0.0252
    assert sigma.shape == (1, 1)
    assert abs(sigma[0, 0] - 0.0001 * 252) < 0.001


def test_covariance_matrix_off_diagonal_independent():
    """Two independent series → off-diagonal ≈ 0."""
    rng = np.random.default_rng(0)
    n_days = 5000  # large for low covariance noise
    daily = pd.DataFrame({
        "X": rng.normal(0, 0.01, n_days),
        "Y": rng.normal(0, 0.01, n_days),
    })
    sigma = covariance_matrix(daily)
    assert sigma.shape == (2, 2)
    # Independent series should have small off-diagonal
    assert abs(sigma[0, 1]) < 0.001
