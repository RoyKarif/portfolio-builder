"""yfinance adapter — single-purpose wrapper around the external library.

This file is the only place in the backend that talks to yfinance.
If yfinance ever changes its API, breaks, or we swap to Alpha Vantage,
the change is contained here.

Public contract: `fetch_price_history(ticker, years) -> list[tuple[date, float]]`.
"""

from datetime import date
import yfinance as yf


class YFinanceError(Exception):
    """Raised when yfinance returns no data or fails."""


def fetch_price_history(ticker: str, years: int = 10) -> list[tuple[date, float]]:
    """Fetch adjusted-close prices for a ticker.

    Returns a list of (date, close_price) tuples, oldest first.

    Raises YFinanceError if the ticker is unknown or no data is returned.
    """
    try:
        history = yf.Ticker(ticker).history(period=f"{years}y", auto_adjust=True)
    except Exception as e:
        raise YFinanceError(f"yfinance failed for {ticker}: {e}") from e

    if history is None or history.empty:
        raise YFinanceError(f"yfinance returned no data for {ticker}")

    # history.index is a DatetimeIndex; convert to plain date.
    # 'Close' is the adjusted close when auto_adjust=True.
    return [
        (idx.date(), float(close))
        for idx, close in history["Close"].items()
        if close is not None and not _is_nan(close)
    ]


def _is_nan(x: float) -> bool:
    """Local NaN check to avoid importing math just for this."""
    return x != x
