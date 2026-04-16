from unittest.mock import patch, MagicMock
from datetime import date

import pandas as pd

from app.data.market import fetch_stock_data, get_cached_or_fetch


def _mock_yf_download(tickers, start, end, **kwargs):
    """Return a DataFrame shaped like yfinance output."""
    dates = pd.date_range(start, end, freq="B")[:5]
    data = {
        "Open": [100.0] * 5,
        "High": [105.0] * 5,
        "Low": [95.0] * 5,
        "Close": [102.0] * 5,
        "Volume": [1000000] * 5,
    }
    return pd.DataFrame(data, index=dates)


@patch("app.data.market.yf.download", side_effect=_mock_yf_download)
def test_fetch_stock_data(mock_download):
    df = fetch_stock_data("AAPL", start="2024-01-01", end="2024-01-10")
    assert len(df) == 5
    assert "Close" in df.columns
    mock_download.assert_called_once()


@patch("app.data.market.yf.download", side_effect=_mock_yf_download)
def test_get_cached_or_fetch_calls_yfinance_on_miss(mock_download, db):
    df = get_cached_or_fetch(db, "AAPL", start="2024-01-01", end="2024-01-10")
    assert len(df) == 5
    mock_download.assert_called_once()
