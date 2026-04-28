"""Portfolio repository — DB access for the `portfolios` table."""

from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio


def save_portfolio(
    db: Session,
    *,
    user_id: int,
    name: str,
    amount: Decimal,
    risk_level: int,
    horizon_years: int,
    target_volatility: float,
    weights: dict[str, float],
    expected_return: float,
    expected_volatility: float,
    sharpe_ratio: float,
    mc_summary: dict,
    mc_seed: int,
) -> Portfolio:
    """Persist a built portfolio.

    Forced kwarg-only (the leading `*`) — too many parameters to allow
    positional, would be error-prone.
    """
    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        amount=amount,
        risk_level=risk_level,
        horizon_years=horizon_years,
        target_volatility=Decimal(str(target_volatility)),
        weights=weights,
        expected_return=Decimal(str(expected_return)),
        expected_volatility=Decimal(str(expected_volatility)),
        sharpe_ratio=Decimal(str(sharpe_ratio)),
        mc_summary=mc_summary,
        mc_seed=mc_seed,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def get_portfolio(db: Session, portfolio_id: int, user_id: int) -> Portfolio | None:
    """Fetch one portfolio, but only if it belongs to the given user.

    The user_id filter prevents user A from accessing user B's portfolios
    by guessing IDs. Authorization at the data layer.
    """
    return (
        db.query(Portfolio)
          .filter(Portfolio.id == portfolio_id, Portfolio.user_id == user_id)
          .one_or_none()
    )


def list_user_portfolios(db: Session, user_id: int) -> list[Portfolio]:
    """All portfolios a user has built, newest first."""
    return (
        db.query(Portfolio)
          .filter(Portfolio.user_id == user_id)
          .order_by(Portfolio.created_at.desc())
          .all()
    )


def delete_portfolio(db: Session, portfolio_id: int, user_id: int) -> bool:
    """Delete a portfolio. Returns True if deleted, False if not found.

    Same authorization principle: user_id must match.
    """
    portfolio = get_portfolio(db, portfolio_id, user_id)
    if portfolio is None:
        return False
    db.delete(portfolio)
    db.commit()
    return True
