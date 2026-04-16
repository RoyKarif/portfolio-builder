from unittest.mock import patch

from app.engine.universe import select_universe


def _mock_fetch_info(ticker: str) -> dict:
    stock_db = {
        "AAPL": {"company_name": "Apple", "sector": "Technology", "exchange": "NMS", "average_volume": 50_000_000},
        "MSFT": {"company_name": "Microsoft", "sector": "Technology", "exchange": "NMS", "average_volume": 30_000_000},
        "JNJ": {"company_name": "Johnson & Johnson", "sector": "Healthcare", "exchange": "NYSE", "average_volume": 8_000_000},
        "XOM": {"company_name": "Exxon Mobil", "sector": "Energy", "exchange": "NYSE", "average_volume": 15_000_000},
        "TEVA": {"company_name": "Teva", "sector": "Healthcare", "exchange": "TLV", "average_volume": 5_000_000},
        "TINY": {"company_name": "TinyStock", "sector": "Technology", "exchange": "NMS", "average_volume": 1_000},
    }
    return stock_db.get(ticker, {"company_name": ticker, "sector": "Unknown", "exchange": "UNKNOWN", "average_volume": 0})


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers", return_value=["AAPL", "MSFT", "JNJ", "XOM", "TEVA", "TINY"])
def test_filter_by_country_us(mock_tickers, mock_info):
    result = select_universe(country="US", sectors=["Technology", "Healthcare"], include_tickers=[], exclude_tickers=[])
    tickers = [s["ticker"] for s in result]
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    assert "JNJ" in tickers
    assert "TEVA" not in tickers
    assert "TINY" not in tickers


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers", return_value=["AAPL", "MSFT", "JNJ", "XOM", "TEVA", "TINY"])
def test_include_exclude_tickers(mock_tickers, mock_info):
    result = select_universe(country="US", sectors=["Technology"], include_tickers=["XOM"], exclude_tickers=["MSFT"])
    tickers = [s["ticker"] for s in result]
    assert "XOM" in tickers
    assert "MSFT" not in tickers


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers", return_value=["AAPL", "MSFT", "JNJ"])
def test_filter_by_sector(mock_tickers, mock_info):
    result = select_universe(country="US", sectors=["Healthcare"], include_tickers=[], exclude_tickers=[])
    tickers = [s["ticker"] for s in result]
    assert "JNJ" in tickers
    assert "AAPL" not in tickers
