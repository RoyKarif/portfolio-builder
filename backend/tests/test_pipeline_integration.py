from unittest.mock import patch

import numpy as np
import pandas as pd

from app.engine.pipeline import generate_portfolio


def _fake_yf_download(tickers, start, end, **kwargs):
    """Build a deterministic synthetic OHLCV panel matching yfinance's
    multi-ticker output shape (MultiIndex columns: (ticker, field))."""
    rng = np.random.default_rng(seed=7)
    n_days = 520
    dates = pd.bdate_range(end=end, periods=n_days)
    frames = []
    for t in tickers:
        base = 100.0
        returns = rng.normal(0.0003, 0.015, n_days)
        prices = base * np.cumprod(1 + returns)
        df = pd.DataFrame(
            {"Close": prices, "Volume": np.full(n_days, 1_000_000.0)},
            index=dates,
        )
        frames.append(df)
    result = pd.concat(frames, axis=1, keys=tickers)
    return result


def _fake_universe(country, sectors, include_tickers, exclude_tickers):
    return [
        {"ticker": f"T{i}", "company_name": f"Co{i}", "sector": "Technology", "exchange": ""}
        for i in range(10)
    ]


@patch("app.engine.pipeline.select_universe", side_effect=_fake_universe)
@patch("app.engine.pipeline.yf.download", side_effect=_fake_yf_download)
def test_pipeline_end_to_end_includes_covariance_metadata(mock_dl, mock_uni):
    result = generate_portfolio(
        country="US",
        risk_level=3,
        investment_horizon="3-5y",
        available_amount=10_000.0,
        target_return=10.0,
        preferred_sectors=["Technology"],
        include_tickers=[],
        exclude_tickers=[],
        db=None,
    )

    assert "error" not in result, f"pipeline returned error: {result.get('error')}"
    assert result["covariance_method"] == "ledoit_wolf"
    assert 0.0 <= result["shrinkage_intensity"] <= 1.0

    total_alloc = sum(h["allocation_pct"] for h in result["holdings"])
    assert abs(total_alloc - 100.0) < 0.5, f"allocations sum to {total_alloc}"
    assert all(h["allocation_pct"] >= 0 for h in result["holdings"])
    # MAX_SINGLE_WEIGHT in optimizer.py is 0.30 → 30% as a pct
    assert all(h["allocation_pct"] <= 30.01 for h in result["holdings"])
