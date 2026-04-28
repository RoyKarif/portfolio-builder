"""Manual bulk seed — pre-warms the price cache for all curated assets.

USAGE NOTE: as of the lazy-fetch refactor, this script is OPTIONAL.
The build endpoint auto-fetches what it needs when you click "Build"
in the UI. This script is useful when you want to pre-warm everything
once, off the critical path.

Run with: `make seed` (or `python -m scripts.seed_universe` inside
the container).

Pass `--synthetic` to skip yfinance entirely and use simulated data.

Idempotent.
"""

from __future__ import annotations
import sys

from app.data import asset_repo, price_repo, yfinance_client
from app.data.universe_definition import CURATED_UNIVERSE
from app.db import SessionLocal
from scripts.synthetic_prices import synthetic_price_history


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
            elif kind == "synthetic":
                synthetic_count += 1
        print()
        print(f"✅ seeded {len(CURATED_UNIVERSE)} assets "
              f"({real_count} real, {synthetic_count} synthetic).")
        if synthetic_count > 0:
            print("⚠ some assets used SYNTHETIC data (yfinance was unavailable).")
    finally:
        db.close()


def _seed_one(db, ticker, name, asset_class, force_synthetic: bool) -> str:
    """Seed a single asset. Returns 'real' or 'synthetic'."""
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
