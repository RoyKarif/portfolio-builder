"""Asset repository — DB access for the `assets` table."""

from sqlalchemy.orm import Session
from app.models.asset import Asset


def get_curated_assets(db: Session) -> list[Asset]:
    """Return the 20 curated ETFs (used by /api/universe).

    Sort by ticker for stable, deterministic UI rendering.
    """
    return (
        db.query(Asset)
          .filter(Asset.is_curated.is_(True))
          .order_by(Asset.ticker)
          .all()
    )


def get_asset_by_ticker(db: Session, ticker: str) -> Asset | None:
    """Look up a single asset by its ticker."""
    return db.query(Asset).filter(Asset.ticker == ticker).one_or_none()


def create_asset(
    db: Session,
    ticker: str,
    name: str,
    asset_class: str,
    is_curated: bool = False,
) -> Asset:
    """Insert a new asset.

    Used by the seed script (is_curated=True) and when a user adds a
    custom ticker via yfinance (is_curated=False).
    """
    asset = Asset(
        ticker=ticker,
        name=name,
        asset_class=asset_class,
        is_curated=is_curated,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def list_assets_by_tickers(db: Session, tickers: list[str]) -> list[Asset]:
    """Return all assets whose ticker is in the given list.

    Used to validate that a list of tickers exists before computing
    a portfolio.
    """
    if not tickers:
        return []
    return db.query(Asset).filter(Asset.ticker.in_(tickers)).all()
