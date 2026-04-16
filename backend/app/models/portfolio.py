import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investment_profiles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="active")
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2))
    expected_return_low: Mapped[float] = mapped_column(Numeric(5, 2))
    expected_return_high: Mapped[float] = mapped_column(Numeric(5, 2))
    total_value: Mapped[float] = mapped_column(Numeric(14, 2))

    user = relationship("User", back_populates="portfolios")
    profile = relationship("InvestmentProfile", back_populates="portfolios")
    holdings = relationship("PortfolioHolding", back_populates="portfolio")
    snapshots = relationship("PortfolioSnapshot", back_populates="portfolio")


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"))
    ticker: Mapped[str] = mapped_column(String(10))
    company_name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(100))
    allocation_pct: Mapped[float] = mapped_column(Numeric(5, 2))
    expected_return: Mapped[float] = mapped_column(Numeric(5, 2))

    portfolio = relationship("Portfolio", back_populates="holdings")
