from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.models.market_data import MarketDataCache


def fetch_stock_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch historical OHLCV data from yfinance."""
    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    return df


def get_cached_or_fetch(db: Session, ticker: str, start: str, end: str) -> pd.DataFrame:
    """Return market data from cache if fresh, otherwise fetch and cache."""
    cached = (
        db.query(MarketDataCache)
        .filter(
            MarketDataCache.ticker == ticker,
            MarketDataCache.date >= date.fromisoformat(start),
            MarketDataCache.date <= date.fromisoformat(end),
        )
        .all()
    )

    if cached:
        latest = max(c.last_updated for c in cached)
        if datetime.utcnow() - latest < timedelta(hours=24):
            return pd.DataFrame(
                [{"Date": c.date, "Open": float(c.open), "High": float(c.high),
                  "Low": float(c.low), "Close": float(c.close), "Volume": c.volume}
                 for c in cached]
            ).set_index("Date")

    df = fetch_stock_data(ticker, start=start, end=end)
    _save_to_cache(db, ticker, df)
    return df


def _save_to_cache(db: Session, ticker: str, df: pd.DataFrame) -> None:
    """Upsert market data rows into cache."""
    for idx, row in df.iterrows():
        row_date = idx.date() if hasattr(idx, "date") else idx
        existing = (
            db.query(MarketDataCache)
            .filter(MarketDataCache.ticker == ticker, MarketDataCache.date == row_date)
            .first()
        )
        if existing:
            existing.open = float(row["Open"])
            existing.high = float(row["High"])
            existing.low = float(row["Low"])
            existing.close = float(row["Close"])
            existing.volume = int(row["Volume"])
            existing.last_updated = datetime.utcnow()
        else:
            db.add(MarketDataCache(
                ticker=ticker, date=row_date,
                open=float(row["Open"]), high=float(row["High"]),
                low=float(row["Low"]), close=float(row["Close"]),
                volume=int(row["Volume"]), last_updated=datetime.utcnow(),
            ))
    db.commit()


def fetch_stock_info(ticker: str) -> dict:
    """Fetch fundamental info (P/E, P/B, dividend yield, sector, name)."""
    stock = yf.Ticker(ticker)
    info = stock.info
    return {
        "company_name": info.get("shortName", ticker),
        "sector": info.get("sector", "Unknown"),
        "pe_ratio": info.get("trailingPE"),
        "pb_ratio": info.get("priceToBook"),
        "dividend_yield": info.get("dividendYield"),
        "market_cap": info.get("marketCap"),
        "average_volume": info.get("averageVolume"),
        "exchange": info.get("exchange", ""),
    }
