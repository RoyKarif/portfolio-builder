import numpy as np
import pytest

from app.engine.hrp import hrp_weights


def test_weights_sum_to_one():
    # 4 uncorrelated assets with equal variance -> equal-weight expected
    cov = np.eye(4) * 0.04  # 20% annualized vol each
    tickers = ["A", "B", "C", "D"]

    weights = hrp_weights(cov, tickers)

    assert set(weights.keys()) == set(tickers)
    assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_all_weights_strictly_positive():
    cov = np.eye(4) * 0.04
    tickers = ["A", "B", "C", "D"]

    weights = hrp_weights(cov, tickers)

    assert all(w > 0 for w in weights.values())


def test_zero_variance_asset_raises():
    cov = np.eye(4) * 0.04
    cov[0, 0] = 0.0  # degenerate asset
    cov[0, 1:] = 0.0
    cov[1:, 0] = 0.0
    tickers = ["A", "B", "C", "D"]

    with pytest.raises(ValueError, match="non-positive or near-zero variance"):
        hrp_weights(cov, tickers)


def test_near_zero_variance_asset_raises():
    cov = np.eye(4) * 0.04
    cov[0, 0] = 1e-15  # below the 1e-12 threshold
    tickers = ["A", "B", "C", "D"]

    with pytest.raises(ValueError, match="non-positive or near-zero variance"):
        hrp_weights(cov, tickers)


def test_too_few_assets_raises():
    cov = np.array([[0.04]])
    tickers = ["A"]

    with pytest.raises(ValueError, match="at least 2 assets"):
        hrp_weights(cov, tickers)


def test_shape_mismatch_raises():
    cov = np.eye(3) * 0.04
    tickers = ["A", "B"]  # length 2 but cov is 3x3

    with pytest.raises(ValueError, match="does not match"):
        hrp_weights(cov, tickers)


def test_determinism_byte_identical_weights():
    rng = np.random.default_rng(seed=42)
    raw = rng.standard_normal((300, 8))
    cov = np.cov(raw, rowvar=False)
    tickers = [f"T{i}" for i in range(8)]

    w1 = hrp_weights(cov, tickers)
    w2 = hrp_weights(cov, tickers)

    # Exact equality, not approximate — single linkage is deterministic
    assert w1 == w2
    for t in tickers:
        assert w1[t] == w2[t]


def test_correlated_assets_share_cluster_weight():
    """Assets 0/1 are highly correlated, 2/3 are nearly independent of them.
    HRP should allocate roughly half the total weight to the {0,1} cluster
    and roughly half to the {2,3} cluster, NOT pile everything on the
    lowest-variance single asset."""
    # Build a covariance matrix with a clear two-cluster block structure
    cov = np.array([
        [0.04, 0.038, 0.001, 0.001],
        [0.038, 0.04, 0.001, 0.001],
        [0.001, 0.001, 0.04, 0.001],
        [0.001, 0.001, 0.001, 0.04],
    ])
    tickers = ["A0", "A1", "B0", "B1"]

    weights = hrp_weights(cov, tickers)

    cluster_a = weights["A0"] + weights["A1"]
    cluster_b = weights["B0"] + weights["B1"]

    # Each cluster should hold a meaningful share of total weight (within 20pp).
    # The exact split depends on cluster variance ratios — for this matrix,
    # cluster B (lower internal correlation) gets ~0.66, cluster A ~0.34.
    # The test guarantees neither cluster is crushed below 30% or above 70%.
    assert 0.30 < cluster_a < 0.70, f"cluster A weight {cluster_a:.3f} not balanced"
    assert 0.30 < cluster_b < 0.70, f"cluster B weight {cluster_b:.3f} not balanced"

    # And no single asset should receive an extreme allocation
    assert all(w < 0.6 for w in weights.values())
