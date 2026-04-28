"""Price repository — DB access for the `prices` table.

This is the bridge between SQL and pandas. The engine works with
DataFrames; SQL stores rows. This module converts.
"""

from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import pandas as pd

from app.models.price import Price


def get_price_history(
    db: Session,
    tickers: list[str],
    years: int = 10,
) -> pd.DataFrame:
    """Return a DataFrame indexed by date, columns=tickers, values=close.

    Shape after pivot:

        ticker      SPY     AGG     ...
        date
        2016-01-04  185.21  108.10  ...
        2016-01-05  185.65  108.34  ...
        ...

    `dropna()` removes any date where at least one ticker is missing,
    so all returned series are aligned (a hard requirement for computing
    a covariance matrix).
    """
    if not tickers:
        return pd.DataFrame()

    cutoff = date.today() - timedelta(days=years * 365)

    rows = (
        db.query(Price.date, Price.ticker, Price.close)
          .filter(Price.ticker.in_(tickers))
          .filter(Price.date >= cutoff)
          .order_by(Price.date)
          .all()
    )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["date", "ticker", "close"])
    # Decimal -> float; numpy can't deal with Decimal in matrix math.
    df["close"] = df["close"].astype(float)
    pivoted = df.pivot(index="date", columns="ticker", values="close")
    return pivoted.dropna()


def bulk_insert_prices(
    db: Session,
    ticker: str,
    rows: list[tuple[date, Decimal | float]],
) -> int:
    """Insert many price rows for one ticker. Returns count inserted.

    Uses bulk_save_objects for speed (one INSERT per row, but no per-row
    Python overhead). For the seed script, this matters: 25 tickers ×
    2,500 rows = 62K inserts.

    Skips rows whose (ticker, date) already exists — idempotent.
    Caller commits.
    """
    # Find existing dates so we don't violate the PK.
    existing_dates = {
        d for (d,) in db.query(Price.date).filter(Price.ticker == ticker).all()
    }

    new_rows = [
        Price(ticker=ticker, date=d, close=Decimal(str(c)))
        for d, c in rows
        if d not in existing_dates
    ]

    if new_rows:
        db.bulk_save_objects(new_rows)

    return len(new_rows)


def latest_price_date(db: Session, ticker: str) -> date | None:
    """Most recent date we have a price for. None if no rows exist.

    Used by the freshness check before deciding whether to re-fetch
    from yfinance.
    """
    result = (
        db.query(Price.date)
          .filter(Price.ticker == ticker)
          .order_by(Price.date.desc())
          .first()
    )
    return result[0] if result else None
