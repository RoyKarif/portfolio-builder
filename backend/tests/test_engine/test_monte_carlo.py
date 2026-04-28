"""Tests for engine.monte_carlo."""

import numpy as np
import pytest

from app.engine.monte_carlo import simulate_portfolio, summarize, histogram_bins


def test_monte_carlo_reproducible_with_same_seed():
    """Same seed → identical output, byte-for-byte."""
    args = dict(
        weights=np.array([0.5, 0.5]),
        mu_annual=np.array([0.08, 0.05]),
        sigma_annual=np.eye(2) * 0.04,
        initial_value=10_000.0,
        horizon_years=5,
        num_paths=1000,
        seed=42,
    )
    a, _ = simulate_portfolio(**args)
    b, _ = simulate_portfolio(**args)
    np.testing.assert_array_equal(a, b)


def test_monte_carlo_different_seeds_differ():
    args = dict(
        weights=np.array([1.0]),
        mu_annual=np.array([0.05]),
        sigma_annual=np.array([[0.04]]),
        initial_value=10_000.0,
        horizon_years=5,
        num_paths=1000,
    )
    a, _ = simulate_portfolio(**args, seed=1)
    b, _ = simulate_portfolio(**args, seed=2)
    assert not np.array_equal(a, b)


def test_monte_carlo_mean_close_to_expected_drift():
    """In a large simulation, mean log-return ≈ μT."""
    mu = np.array([0.10])
    sigma = np.array([[0.04]])
    weights = np.array([1.0])
    initial = 10_000.0
    years = 5

    final_values, _ = simulate_portfolio(
        weights, mu, sigma, initial, years,
        num_paths=20_000, seed=1,
    )

    # E[V_T] under log-normal = V_0 * exp(μT) when r_t ~ N(μ_d, σ_d²)
    # with μ_d = μ/252, σ_d² = σ²/252. The total log-return over T years
    # is Normal(μT, σ²T), and the final value V_0 * exp(R_total).
    # Mean of the *log* of final values ≈ μT.
    log_final = np.log(final_values / initial)
    expected_mean_log = mu[0] * years
    assert abs(log_final.mean() - expected_mean_log) < 0.1


def test_summarize_percentiles_ordered():
    """p5 < p25 < p50 < p75 < p95 must always hold."""
    weights = np.array([0.5, 0.5])
    mu = np.array([0.08, 0.05])
    sigma = np.eye(2) * 0.04
    initial = 10_000.0
    years = 10
    final_values, cumulative = simulate_portfolio(
        weights, mu, sigma, initial, years,
        num_paths=5000, seed=42,
    )
    s = summarize(final_values, cumulative, initial, years)
    assert s["p5"] < s["p25"] < s["p50"] < s["p75"] < s["p95"]


def test_summarize_timeline_starts_at_initial_value():
    """Year 0 of the timeline is just the initial value (no uncertainty yet)."""
    weights = np.array([1.0])
    mu = np.array([0.05])
    sigma = np.array([[0.04]])
    initial = 10_000.0
    final_values, cumulative = simulate_portfolio(
        weights, mu, sigma, initial, 5,
        num_paths=1000, seed=42,
    )
    s = summarize(final_values, cumulative, initial, 5)
    timeline = s["timeline"]
    assert timeline[0]["year"] == 0
    assert timeline[0]["p5"] == initial
    assert timeline[0]["p95"] == initial
    # Last entry is year 5
    assert timeline[-1]["year"] == 5


def test_histogram_bins_shape():
    rng = np.random.default_rng(0)
    values = rng.normal(10000, 1000, 1000)
    h = histogram_bins(values, num_bins=20)
    assert len(h["counts"]) == 20
    assert len(h["edges"]) == 21
    assert sum(h["counts"]) == len(values)
