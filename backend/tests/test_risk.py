import numpy as np
import pandas as pd
import pytest

from app.engine.risk import estimate_covariance


@pytest.fixture
def synthetic_returns():
    rng = np.random.default_rng(seed=42)
    data = rng.multivariate_normal(
        mean=np.zeros(5),
        cov=np.eye(5) * 0.0004,
        size=200,
    )
    return pd.DataFrame(data, columns=["A", "B", "C", "D", "E"])


def test_happy_path_shape_and_types(synthetic_returns):
    cov, shrinkage, meta = estimate_covariance(synthetic_returns)
    assert cov.shape == (5, 5)
    assert np.allclose(cov, cov.T)
    assert isinstance(shrinkage, float)
    assert 0.0 <= shrinkage <= 1.0
    assert meta["method"] == "ledoit_wolf"
    assert meta["n_tickers"] == 5
    assert meta["n_observations"] == 200
    assert meta["dropped_tickers"] == []
    assert meta["fallback_used"] is False
    assert meta["fallback_reason"] is None


def test_psd_within_tolerance(synthetic_returns):
    cov, _, _ = estimate_covariance(synthetic_returns)
    assert float(np.linalg.eigvalsh(cov).min()) > -1e-8
