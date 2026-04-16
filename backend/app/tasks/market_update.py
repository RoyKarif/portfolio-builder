from datetime import datetime, timedelta

from app.database import SessionLocal
from app.data.market import fetch_stock_data, _save_to_cache
from app.models.portfolio import Portfolio, PortfolioHolding
from app.tasks.celery_app import celery_app


@celery_app.task
def update_all_market_data():
    db = SessionLocal()
    try:
        active_portfolios = db.query(Portfolio).filter(Portfolio.status == "active").all()
        ticker_set = set()
        for portfolio in active_portfolios:
            holdings = db.query(PortfolioHolding).filter(
                PortfolioHolding.portfolio_id == portfolio.id
            ).all()
            for h in holdings:
                ticker_set.add(h.ticker)

        end_date = datetime.utcnow().strftime("%Y-%m-%d")
        start_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        for ticker in ticker_set:
            try:
                df = fetch_stock_data(ticker, start=start_date, end=end_date)
                _save_to_cache(db, ticker, df)
            except Exception:
                continue
    finally:
        db.close()
