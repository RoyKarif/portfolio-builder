"""Smart price-cache management.

For every ticker we serve from MVO/Monte Carlo, we want:
  - The historical 10y series (for μ and Σ).
  - That series to be FRESH — i.e., include the most recent trading day.

Strategy implemented here (`ensure_prices_fresh`):
  1. Look at each requested ticker's `latest_price_date` in the DB.
  2. If missing → fetch full 10y from yfinance.
  3. If older than `max_staleness_days` (default = 1 day) → fetch the
     gap (only the new days since `latest_date + 1`).
  4. Otherwise → cache hit, do nothing.

Fetches run in parallel via a ThreadPoolExecutor (yfinance is sync;
threading is the easy way to get concurrency without rewriting it).

DB writes happen on the main thread after each future completes
(SQLAlchemy sessions are not thread-safe).

If yfinance fails for any ticker, we fall back to synthetic prices
generated from Geometric Brownian Motion with realistic per-class
(μ, σ) — so the demo always works.
"""

from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.data import asset_repo, price_repo, yfinance_client
from scripts.synthetic_prices import synthetic_price_history

log = logging.getLogger(__name__)


def ensure_prices_fresh(
    db: Session,
    tickers: list[str],
    max_staleness_days: int = 1,
) -> dict:
    """Make sure every requested ticker has price data not older than
    `max_staleness_days`.

    Returns a summary dict for logging:
        {
            "fresh":     [tickers already up to date],
            "fetched":   [tickers refreshed from yfinance],
            "synthetic": [tickers filled with synthetic data],
            "failed":    [(ticker, error_message), ...],
        }
    """
    today = date.today()
    cutoff = today - timedelta(days=max_staleness_days)

    summary: dict = {
        "fresh": [],
        "fetched": [],
        "synthetic": [],
        "failed": [],
    }

    # Step 1: Decide what each ticker needs. Done sequentially on the
    # main thread (cheap queries).
    work_items: list[tuple[str, str, str]] = []  # (ticker, mode, asset_class)
    for ticker in tickers:
        latest = price_repo.latest_price_date(db, ticker)
        asset = asset_repo.get_asset_by_ticker(db, ticker)
        asset_class = asset.asset_class if asset else "equity"

        if latest is None:
            work_items.append((ticker, "full", asset_class))
        elif latest < cutoff:
            work_items.append((ticker, "incremental", asset_class))
        else:
            summary["fresh"].append(ticker)

    if not work_items:
        return summary  # everything already cached and fresh

    # Step 2: Fire all fetches in parallel.
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_meta = {
            executor.submit(_fetch_one, ticker, mode, asset_class):
                (ticker, mode, asset_class)
            for ticker, mode, asset_class in work_items
        }

        # Step 3: As each future completes, write its rows to the DB
        # on the main thread (sessions are not thread-safe).
        for future in as_completed(future_to_meta):
            ticker, mode, asset_class = future_to_meta[future]
            try:
                rows, source = future.result()
            except Exception as e:
                summary["failed"].append((ticker, str(e)))
                log.warning("ensure_prices_fresh: %s failed: %s", ticker, e)
                continue

            # Make sure the asset row itself exists (custom tickers
            # might not yet be registered).
            if asset_repo.get_asset_by_ticker(db, ticker) is None:
                asset_repo.create_asset(
                    db,
                    ticker=ticker,
                    name=ticker,
                    asset_class=asset_class,
                    is_curated=False,
                )

            inserted = price_repo.bulk_insert_prices(db, ticker, rows)
            db.commit()

            if source == "real":
                summary["fetched"].append(ticker)
            else:
                summary["synthetic"].append(ticker)
            log.info("ensure_prices_fresh: %s %s (%s, +%d rows)",
                     ticker, mode, source, inserted)

    return summary


def _fetch_one(
    ticker: str,
    mode: str,
    asset_class: str,
) -> tuple[list[tuple[date, float]], str]:
    """Fetch one ticker's prices. Runs inside a worker thread.

    Returns (rows, source) where source is 'real' or 'synthetic'.
    """
    # Incremental fetches still pull a generous window (1 year) so we
    # cover any gaps that may have accumulated. yfinance gives us
    # daily bars; bulk_insert_prices skips ones we already have.
    years = 10 if mode == "full" else 1

    try:
        rows = yfinance_client.fetch_price_history(ticker, years=years)
        return rows, "real"
    except yfinance_client.YFinanceError as e:
        log.warning("yfinance failed for %s: %s — using synthetic", ticker, e)
        rows = synthetic_price_history(ticker, asset_class, years=10)
        return rows, "synthetic"
