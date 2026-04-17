from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.engine.screens import apply_quality_screen


def _build_batch(tickers, n_days=520, end=date(2026, 4, 16), volume=1_000_000.0):
    """Build a synthetic yfinance-shaped batch (MultiIndex columns) with a
    deterministic price/volume panel. Each ticker gets identical structure;
    callers can override Close or Volume per ticker via post-processing."""
    rng = np.random.default_rng(seed=42)
    dates = pd.bdate_range(end=end.isoformat(), periods=n_days)
    frames = []
    for t in tickers:
        returns = rng.normal(0.0003, 0.015, n_days)
        prices = 100.0 * np.cumprod(1 + returns)
        df = pd.DataFrame({"Close": prices, "Volume": np.full(n_days, volume)}, index=dates)
        frames.append(df)
    return pd.concat(frames, axis=1, keys=tickers), dates


@pytest.fixture
def cov_cutoff():
    return date(2026, 4, 16) - timedelta(days=2 * 365)


def test_happy_path_all_tickers_survive(cov_cutoff):
    tickers = [f"T{i}" for i in range(10)]
    batch, _ = _build_batch(tickers)

    price_data, dropped = apply_quality_screen(batch, tickers, cov_cutoff)

    assert list(price_data.keys()) == tickers
    assert dropped == []
    for t in tickers:
        assert isinstance(price_data[t], pd.Series)
        assert (price_data[t].index.date >= cov_cutoff).all()
