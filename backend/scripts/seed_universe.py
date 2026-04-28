"""One-time setup: populate the curated universe and download 10 years
of daily prices for each asset.

Run with: `make seed` (or `python -m scripts.seed_universe` inside the
container).

Idempotent: skips assets and prices that already exist. Safe to re-run
after adding a new ticker to CURATED_UNIVERSE.

The 20 ETFs are chosen to span major asset classes / regions / styles,
so MVO has interesting diversification options.
"""

from __future__ import annotations
import sys
import time

from app.data import asset_repo, price_repo, yfinance_client
from app.db import SessionLocal


# (ticker, display_name, asset_class)
CURATED_UNIVERSE: list[tuple[str, str, str]] = [
    # --- US equity, broad ---
    ("SPY", "SPDR S&P 500 ETF", "equity"),
    ("QQQ", "Invesco QQQ (NASDAQ-100)", "equity"),
    ("IWM", "iShares Russell 2000 (Small Cap)", "equity"),
    ("VTI", "Vanguard Total Stock Market", "equity"),
    # --- US equity, sector / style ---
    ("XLK", "Technology Select Sector SPDR", "equity"),
    ("XLF", "Financials Select Sector SPDR", "equity"),
    ("XLE", "Energy Select Sector SPDR", "equity"),
    ("XLV", "Health Care Select Sector SPDR", "equity"),
    # --- International equity ---
    ("EFA", "iShares MSCI EAFE (Developed ex-US)", "equity"),
    ("EEM", "iShares MSCI Emerging Markets", "equity"),
    ("VGK", "Vanguard FTSE Europe", "equity"),
    # --- Bonds ---
    ("AGG", "iShares Core U.S. Aggregate Bond", "bond"),
    ("TLT", "iShares 20+ Year Treasury", "bond"),
    ("LQD", "iShares iBoxx Investment Grade Corporate", "bond"),
    ("HYG", "iShares iBoxx High Yield Corporate", "bond"),
    # --- Commodities ---
    ("GLD", "SPDR Gold Trust", "commodity"),
    ("SLV", "iShares Silver Trust", "commodity"),
    ("DBC", "Invesco DB Commodity Index", "commodity"),
    # --- Real estate ---
    ("VNQ", "Vanguard Real Estate ETF", "real_estate"),
    # --- Cash equivalent ---
    ("BIL", "SPDR 1-3 Month T-Bill", "cash"),
]


def seed() -> None:
    """Run the full seed."""
    db = SessionLocal()
    try:
        for ticker, name, asset_class in CURATED_UNIVERSE:
            _seed_one(db, ticker, name, asset_class)
            # Be polite to yfinance — half-second between requests.
            time.sleep(0.5)
        print(f"\n✅ seeded {len(CURATED_UNIVERSE)} assets.")
    finally:
        db.close()


def _seed_one(db, ticker: str, name: str, asset_class: str) -> None:
    """Seed a single asset. Idempotent."""
    existing = asset_repo.get_asset_by_ticker(db, ticker)
    if existing is None:
        asset_repo.create_asset(
            db,
            ticker=ticker,
            name=name,
            asset_class=asset_class,
            is_curated=True,
        )
        print(f"➕ created asset {ticker}")
    else:
        # If it existed but wasn't curated (e.g. user-added it earlier),
        # promote it to curated.
        if not existing.is_curated:
            existing.is_curated = True
            existing.name = name
            existing.asset_class = asset_class
            db.commit()
            print(f"⬆ promoted {ticker} to curated")

    # Always check if we need more price data.
    print(f"📥 fetching prices for {ticker}…", end=" ", flush=True)
    try:
        rows = yfinance_client.fetch_price_history(ticker, years=10)
    except yfinance_client.YFinanceError as e:
        print(f"❌ skipped: {e}")
        return

    inserted = price_repo.bulk_insert_prices(db, ticker, rows)
    db.commit()
    print(f"✅ {inserted} new rows ({len(rows)} fetched)")


if __name__ == "__main__":
    try:
        seed()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
