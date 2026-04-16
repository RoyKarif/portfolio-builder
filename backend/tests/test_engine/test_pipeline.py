from unittest.mock import patch, MagicMock
import numpy as np
import pandas as pd

from app.engine.pipeline import generate_portfolio


def _mock_select_universe(**kwargs):
    return [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "exchange": "NMS"},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "exchange": "NMS"},
        {"ticker": "JNJ", "company_name": "J&J", "sector": "Healthcare", "exchange": "NYSE"},
        {"ticker": "PG", "company_name": "P&G", "sector": "Consumer", "exchange": "NYSE"},
        {"ticker": "XOM", "company_name": "Exxon", "sector": "Energy", "exchange": "NYSE"},
    ]


def _mock_predict_returns(stocks, db):
    for s in stocks:
        s["expected_return"] = np.random.uniform(0.05, 0.15)
    return stocks


def _mock_fetch_data(ticker, start, end):
    np.random.seed(hash(ticker) % 2**31)
    n = 252
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    prices = 100 * np.cumprod(1 + np.random.normal(0.0004, 0.02, n))
    return pd.DataFrame({"Close": prices}, index=dates)


@patch("app.engine.pipeline.fetch_stock_data", side_effect=_mock_fetch_data)
@patch("app.engine.pipeline.predict_returns", side_effect=_mock_predict_returns)
@patch("app.engine.pipeline.select_universe", side_effect=_mock_select_universe)
def test_generate_portfolio(mock_universe, mock_predict, mock_fetch):
    result = generate_portfolio(
        country="US",
        risk_level=3,
        investment_horizon="3-5y",
        available_amount=50000,
        target_return=0.10,
        preferred_sectors=["Technology", "Healthcare"],
        include_tickers=[],
        exclude_tickers=[],
        db=None,
    )

    assert "holdings" in result
    assert len(result["holdings"]) >= 1
    assert "risk_score" in result
    assert "expected_return_low" in result
    assert "expected_return_high" in result
    assert "simulation" in result

    total_alloc = sum(h["allocation_pct"] for h in result["holdings"])
    assert abs(total_alloc - 100.0) < 1.0
