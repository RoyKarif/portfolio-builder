import numpy as np
from app.engine.simulator import run_monte_carlo


def test_monte_carlo_output_shape():
    weights = np.array([0.3, 0.3, 0.2, 0.2])
    expected_returns = np.array([0.12, 0.10, 0.08, 0.15])
    cov_matrix = np.eye(4) * 0.03

    result = run_monte_carlo(weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix, initial_value=50000, horizon_years=3, n_simulations=1000)

    assert "percentile_10" in result
    assert "percentile_50" in result
    assert "percentile_90" in result
    assert "return_low" in result
    assert "return_high" in result
    assert result["percentile_10"] < result["percentile_50"] < result["percentile_90"]


def test_monte_carlo_reasonable_values():
    weights = np.array([0.5, 0.5])
    expected_returns = np.array([0.10, 0.10])
    cov_matrix = np.array([[0.04, 0.01], [0.01, 0.04]])

    result = run_monte_carlo(weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix, initial_value=100000, horizon_years=5, n_simulations=10000)

    assert 80_000 < result["percentile_50"] < 300_000
    assert result["percentile_10"] > 0


def test_monte_carlo_is_deterministic_for_same_inputs():
    weights = np.array([0.25, 0.25, 0.25, 0.25])
    expected_returns = np.array([0.10, 0.12, 0.08, 0.11])
    cov_matrix = np.eye(4) * 0.04

    a = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=10_000.0, horizon_years=3.0, n_simulations=1_000,
    )
    b = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=10_000.0, horizon_years=3.0, n_simulations=1_000,
    )

    assert a["percentile_10"] == b["percentile_10"]
    assert a["percentile_50"] == b["percentile_50"]
    assert a["percentile_90"] == b["percentile_90"]


def test_monte_carlo_changes_with_inputs():
    weights = np.array([0.25, 0.25, 0.25, 0.25])
    expected_returns = np.array([0.10, 0.12, 0.08, 0.11])
    cov_matrix = np.eye(4) * 0.04

    a = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=10_000.0, horizon_years=3.0, n_simulations=1_000,
    )
    b = run_monte_carlo(
        weights=weights, expected_returns=expected_returns, cov_matrix=cov_matrix,
        initial_value=20_000.0, horizon_years=3.0, n_simulations=1_000,
    )

    assert a["percentile_50"] != b["percentile_50"]
