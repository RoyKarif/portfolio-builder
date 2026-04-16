import numpy as np
import pandas as pd
from unittest.mock import patch

from app.engine.predictor import build_features, predict_returns


def _make_price_series(n_days=252, base_price=100.0, ticker="AAPL"):
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=n_days, freq="B")
    returns = np.random.normal(0.0005, 0.02, n_days)
    prices = base_price * np.cumprod(1 + returns)
    return pd.DataFrame({
        "Close": prices,
        "Volume": np.random.randint(1_000_000, 10_000_000, n_days),
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Open": prices * 1.005,
    }, index=dates)


def test_build_features():
    df = _make_price_series()
    features = build_features(df)
    assert "return_5d" in features.columns
    assert "return_21d" in features.columns
    assert "volatility_21d" in features.columns
    assert "momentum_63d" in features.columns
    assert "sma_50_ratio" in features.columns
    assert len(features) > 0
    assert not features.isnull().all().any()


@patch("app.engine.predictor.fetch_stock_data")
@patch("app.engine.predictor.fetch_stock_info")
def test_predict_returns(mock_info, mock_fetch):
    mock_info.return_value = {"pe_ratio": 25.0, "pb_ratio": 8.0, "dividend_yield": 0.005}
    mock_fetch.return_value = _make_price_series()

    stocks = [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "exchange": "NMS"},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "exchange": "NMS"},
    ]
    result = predict_returns(stocks, db=None)

    assert len(result) == 2
    for stock in result:
        assert "expected_return" in stock
        assert isinstance(stock["expected_return"], float)
