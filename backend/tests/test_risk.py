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


def test_drops_all_nan_column(synthetic_returns):
    df = synthetic_returns.copy()
    df["C"] = np.nan
    cov, _, meta = estimate_covariance(df)
    assert cov.shape == (4, 4)
    assert meta["dropped_tickers"] == ["C"]
    assert meta["n_tickers"] == 4
    assert meta["n_observations"] == 200


def test_drops_rows_with_any_nan(synthetic_returns):
    df = synthetic_returns.copy()
    df.iloc[5:10, 2] = np.nan
    cov, _, meta = estimate_covariance(df)
    assert cov.shape == (5, 5)
    assert meta["n_observations"] == 195
    assert meta["dropped_tickers"] == []


def test_raises_on_too_few_tickers(synthetic_returns):
    df = synthetic_returns[["A"]]
    with pytest.raises(ValueError, match="at least 2 tickers"):
        estimate_covariance(df)


def test_raises_on_too_few_observations(synthetic_returns):
    df = synthetic_returns.iloc[:20]
    with pytest.raises(ValueError, match="at least 30 observations"):
        estimate_covariance(df)


def test_raises_on_non_numeric_column(synthetic_returns):
    df = synthetic_returns.copy()
    df["A"] = "not a number"
    with pytest.raises(ValueError, match="numeric columns"):
        estimate_covariance(df)
