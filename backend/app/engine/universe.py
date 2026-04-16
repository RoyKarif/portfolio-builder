from app.data.country_data import get_allowed_exchanges
from app.data.market import fetch_stock_info

VOLUME_THRESHOLD = 100_000


def select_universe(
    country: str,
    sectors: list[str],
    include_tickers: list[str],
    exclude_tickers: list[str],
) -> list[dict]:
    allowed_exchanges = get_allowed_exchanges(country)
    candidates = set(_get_sector_tickers(sectors))
    candidates.update(include_tickers)
    candidates -= set(exclude_tickers)

    result = []
    for ticker in candidates:
        info = fetch_stock_info(ticker)
        if info.get("exchange", "") not in allowed_exchanges:
            if ticker not in include_tickers:
                continue
        if ticker not in include_tickers and info.get("sector") not in sectors:
            continue
        if info.get("average_volume", 0) < VOLUME_THRESHOLD:
            if ticker not in include_tickers:
                continue
        result.append({
            "ticker": ticker,
            "company_name": info.get("company_name", ticker),
            "sector": info.get("sector", "Unknown"),
            "exchange": info.get("exchange", ""),
        })
    return result


def _get_sector_tickers(sectors: list[str]) -> list[str]:
    import yfinance as yf
    sector_map = {
        "Technology": "technology",
        "Healthcare": "healthcare",
        "Energy": "energy",
        "Finance": "financial-services",
        "Consumer": "consumer-cyclical",
        "Real Estate": "real-estate",
        "Industrial": "industrials",
    }
    tickers = []
    for sector in sectors:
        yf_sector = sector_map.get(sector)
        if not yf_sector:
            continue
        try:
            screener = yf.Sector(yf_sector)
            top = screener.top_companies
            if top is not None and not top.empty:
                tickers.extend(top.index.tolist()[:30])
        except Exception:
            continue
    return list(set(tickers))
