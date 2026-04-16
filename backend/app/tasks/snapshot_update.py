from datetime import date, datetime, timedelta

import yfinance as yf

from app.database import SessionLocal
from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.snapshot import PortfolioSnapshot
from app.tasks.celery_app import celery_app


@celery_app.task
def update_all_snapshots():
    db = SessionLocal()
    try:
        today = date.today()
        active_portfolios = db.query(Portfolio).filter(Portfolio.status == "active").all()

        for portfolio in active_portfolios:
            existing = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.portfolio_id == portfolio.id,
                PortfolioSnapshot.date == today,
            ).first()
            if existing:
                continue

            holdings = db.query(PortfolioHolding).filter(
                PortfolioHolding.portfolio_id == portfolio.id
            ).all()

            total_value = 0.0
            for h in holdings:
                try:
                    ticker = yf.Ticker(h.ticker)
                    price = ticker.info.get("regularMarketPrice", 0)
                    allocated_amount = float(portfolio.total_value) * float(h.allocation_pct) / 100
                    total_value += allocated_amount * (1 + (price / 100 - 1) * 0.01)
                except Exception:
                    total_value += float(portfolio.total_value) * float(h.allocation_pct) / 100

            prev_snapshot = (
                db.query(PortfolioSnapshot)
                .filter(PortfolioSnapshot.portfolio_id == portfolio.id)
                .order_by(PortfolioSnapshot.date.desc())
                .first()
            )
            prev_value = float(prev_snapshot.total_value) if prev_snapshot else float(portfolio.total_value)
            daily_return = (total_value - prev_value) / prev_value if prev_value > 0 else 0

            snapshot = PortfolioSnapshot(
                portfolio_id=portfolio.id,
                date=today,
                total_value=total_value,
                daily_return=daily_return,
            )
            db.add(snapshot)

        db.commit()
    finally:
        db.close()
