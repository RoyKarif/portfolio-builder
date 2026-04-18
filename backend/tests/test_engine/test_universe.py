from unittest.mock import patch

from app.engine.universe import DEFENSIVE_ETFS, select_universe


def _mock_fetch_info(ticker: str) -> dict:
    stock_db = {
        "AAPL": {"company_name": "Apple", "sector": "Technology", "exchange": "NMS"},
        "MSFT": {"company_name": "Microsoft", "sector": "Technology", "exchange": "NMS"},
        "JNJ": {"company_name": "J&J", "sector": "Healthcare", "exchange": "NYSE"},
    }
    return stock_db.get(ticker, {"company_name": ticker, "sector": "Unknown", "exchange": "NMS"})


def _mock_sector_tickers_with_meta(sectors: list[str]) -> list[dict]:
    return [
        {"ticker": "AAPL", "company_name": "Apple", "sector": "Technology", "exchange": ""},
        {"ticker": "MSFT", "company_name": "Microsoft", "sector": "Technology", "exchange": ""},
    ]


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_high_risk_level_excludes_defensives(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=[], risk_level=4,
    )
    tickers = {s["ticker"] for s in result}
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    # Risk level 4 (and 5) must not see any defensive ETFs.
    for etf in DEFENSIVE_ETFS:
        assert etf["ticker"] not in tickers, f"{etf['ticker']} leaked into risk_level=4 universe"


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_low_risk_level_appends_defensives(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=[], risk_level=1,
    )
    tickers = {s["ticker"] for s in result}
    # Sector picks are still there (append, not replace).
    assert "AAPL" in tickers
    assert "MSFT" in tickers
    # All defensives present.
    for etf in DEFENSIVE_ETFS:
        assert etf["ticker"] in tickers, f"defensive {etf['ticker']} missing from risk_level=1 universe"


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_user_include_of_defensive_etf_does_not_duplicate(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=["GLD"], exclude_tickers=[], risk_level=2,
    )
    tickers = [s["ticker"] for s in result]
    # GLD should appear exactly once even though both include_tickers
    # AND the auto-inject loop would normally add it.
    assert tickers.count("GLD") == 1


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_exclude_overrides_auto_inject(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=["AGG"], risk_level=1,
    )
    tickers = {s["ticker"] for s in result}
    # AGG was excluded by the user; auto-inject must respect that.
    assert "AGG" not in tickers
    # The other defensives are still added.
    assert "IEF" in tickers
    assert "GLD" in tickers
    assert "XLU" in tickers
    assert "XLP" in tickers


@patch("app.engine.universe.fetch_stock_info", side_effect=_mock_fetch_info)
@patch("app.engine.universe._get_sector_tickers_with_meta", side_effect=_mock_sector_tickers_with_meta)
def test_is_defensive_flag_set_correctly(mock_sect, mock_info):
    result = select_universe(
        country="US", sectors=["Technology"],
        include_tickers=[], exclude_tickers=[], risk_level=1,
    )
    by_ticker = {s["ticker"]: s for s in result}
    # Regular sector picks have is_defensive=False.
    assert by_ticker["AAPL"]["is_defensive"] is False
    assert by_ticker["MSFT"]["is_defensive"] is False
    # All defensives have is_defensive=True with stable sector labels.
    expected_sectors = {"AGG": "Bonds", "IEF": "Bonds", "GLD": "Commodities",
                        "XLU": "Utilities", "XLP": "Consumer Staples"}
    for etf_ticker, expected_sector in expected_sectors.items():
        entry = by_ticker[etf_ticker]
        assert entry["is_defensive"] is True
        assert entry["sector"] == expected_sector
