"""One-time setup: populate the curated universe and download 10 years
of daily prices for each asset.

Run with: `make seed` (or `python -m scripts.seed_universe` inside the
container).

Strategy:
  1. Try to fetch real prices from yfinance.
  2. If yfinance fails (Yahoo's API breaks regularly), fall back to
     synthetic prices generated with GBM and realistic per-class μ/σ.
     The synthetic data is deterministic (seeded by ticker hash) so
     re-runs are reproducible.

Idempotent: skips assets and prices that already exist. Safe to re-run
after adding a new ticker to CURATED_UNIVERSE.

Pass --synthetic on the command line to skip yfinance entirely.
"""

from __future__ import annotations
import sys
import time

from app.data import asset_repo, price_repo, yfinance_client
from app.db import SessionLocal
from scripts.synthetic_prices import synthetic_price_history


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


def seed(force_synthetic: bool = False) -> None:
    """Run the full seed."""
    db = SessionLocal()
    real_count = 0
    synthetic_count = 0
    try:
        for ticker, name, asset_class in CURATED_UNIVERSE:
            kind = _seed_one(db, ticker, name, asset_class, force_synthetic)
            if kind == "real":
                real_count += 1
                time.sleep(0.5)  # be polite to yfinance
            elif kind == "synthetic":
                synthetic_count += 1
        print()
        print(f"✅ seeded {len(CURATED_UNIVERSE)} assets "
              f"({real_count} real, {synthetic_count} synthetic).")
        if synthetic_count > 0:
            print("⚠ some assets used SYNTHETIC data (yfinance was unavailable).")
            print("  This is fine for a demo, but the prices are simulated.")
    finally:
        db.close()


def _seed_one(db, ticker, name, asset_class, force_synthetic: bool) -> str:
    """Seed a single asset. Returns 'real' or 'synthetic' depending on data source."""
    existing = asset_repo.get_asset_by_ticker(db, ticker)
    if existing is None:
        asset_repo.create_asset(
            db, ticker=ticker, name=name,
            asset_class=asset_class, is_curated=True,
        )
        print(f"➕ created asset {ticker}")
    elif not existing.is_curated:
        existing.is_curated = True
        existing.name = name
        existing.asset_class = asset_class
        db.commit()
        print(f"⬆ promoted {ticker} to curated")

    # Decide source: try yfinance unless forced to synthetic.
    rows = None
    source = "synthetic"
    if not force_synthetic:
        print(f"📥 fetching prices for {ticker} from yfinance...", end=" ", flush=True)
        try:
            rows = yfinance_client.fetch_price_history(ticker, years=10)
            source = "real"
            print(f"✅ {len(rows)} rows")
        except yfinance_client.YFinanceError as e:
            print(f"⚠ yfinance failed ({e}) — falling back to synthetic")

    if rows is None:
        print(f"🎲 generating synthetic 10y for {ticker} ({asset_class})...", end=" ", flush=True)
        rows = synthetic_price_history(ticker, asset_class, years=10)
        print(f"✅ {len(rows)} rows")

    inserted = price_repo.bulk_insert_prices(db, ticker, rows)
    db.commit()
    print(f"   → inserted {inserted} new price rows")
    return source


if __name__ == "__main__":
    force_synthetic = "--synthetic" in sys.argv
    if force_synthetic:
        print("ℹ Running in SYNTHETIC mode (yfinance skipped).\n")
    try:
        seed(force_synthetic=force_synthetic)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)
