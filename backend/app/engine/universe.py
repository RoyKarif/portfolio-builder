from app.data.country_data import get_allowed_exchanges
from app.data.market import fetch_stock_info


DEFENSIVE_ETFS: list[dict] = [
    {"ticker": "AGG", "company_name": "iShares Core US Aggregate Bond ETF",
     "sector": "Bonds", "exchange": "", "is_defensive": True},
    {"ticker": "IEF", "company_name": "iShares 7-10 Year Treasury Bond ETF",
     "sector": "Bonds", "exchange": "", "is_defensive": True},
    {"ticker": "GLD", "company_name": "SPDR Gold Trust",
     "sector": "Commodities", "exchange": "", "is_defensive": True},
    {"ticker": "XLU", "company_name": "Utilities Select Sector SPDR Fund",
     "sector": "Utilities", "exchange": "", "is_defensive": True},
    {"ticker": "XLP", "company_name": "Consumer Staples Select Sector SPDR Fund",
     "sector": "Consumer Staples", "exchange": "", "is_defensive": True},
]


def select_universe(
    country: str,
    sectors: list[str],
    include_tickers: list[str],
    exclude_tickers: list[str],
    risk_level: int,
) -> list[dict]:
    """Build the candidate stock universe.

    yf.Sector already returns top US-listed companies in each sector, so we
    trust those without per-ticker yfinance validation (which was causing
    rate-limits → empty results). User-provided include_tickers are still
    validated via fetch_stock_info so we have proper company names.

    When risk_level <= 3, append a small fixed set of defensive ETFs to
    the candidate universe (per the defensive-universe spec). Defensives
    are appended, not replaced over user picks, and respect the user's
    exclude_tickers and include_tickers.
    """
    allowed_exchanges = set(get_allowed_exchanges(country))
    excluded = set(exclude_tickers)
    sector_tickers_with_meta = _get_sector_tickers_with_meta(sectors)

    result = []
    seen = set()
    for entry in sector_tickers_with_meta:
        ticker = entry["ticker"]
        if ticker in excluded or ticker in seen:
            continue
        seen.add(ticker)
        entry["is_defensive"] = False
        result.append(entry)

    for ticker in include_tickers:
        if ticker in excluded or ticker in seen:
            continue
        seen.add(ticker)
        info = fetch_stock_info(ticker)
        if info.get("exchange") and info["exchange"] not in allowed_exchanges:
            continue
        result.append({
            "ticker": ticker,
            "company_name": info.get("company_name", ticker),
            "sector": info.get("sector", "Unknown"),
            "exchange": info.get("exchange", ""),
            "is_defensive": False,
        })

    # Auto-inject defensive ETFs for conservative-to-moderate profiles.
    # Appended to the existing selection; reuses `seen` and `excluded` so
    # user-supplied includes aren't duplicated and excludes still win.
    if risk_level <= 3:
        for etf in DEFENSIVE_ETFS:
            if etf["ticker"] in excluded or etf["ticker"] in seen:
                continue
            seen.add(etf["ticker"])
            result.append(dict(etf))  # copy so callers can't mutate the constant

    return result


SECTOR_MAP = {
    "Technology": "technology",
    "Healthcare": "healthcare",
    "Energy": "energy",
    "Finance": "financial-services",
    "Consumer": "consumer-cyclical",
    "Real Estate": "real-estate",
    "Industrial": "industrials",
}


def _get_sector_tickers_with_meta(sectors: list[str]) -> list[dict]:
    """Return top companies per sector with name + sector metadata from yfinance."""
    import yfinance as yf
    out: list[dict] = []
    for sector in sectors:
        yf_sector = SECTOR_MAP.get(sector)
        if not yf_sector:
            continue
        try:
            top = yf.Sector(yf_sector).top_companies
        except Exception:
            continue
        if top is None or top.empty:
            continue
        for symbol, row in top.head(15).iterrows():
            out.append({
                "ticker": symbol,
                "company_name": row.get("name", symbol),
                "sector": sector,
                "exchange": "",
            })
    return out
