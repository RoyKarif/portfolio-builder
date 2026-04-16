from datetime import date, datetime

from sqlalchemy import String, Numeric, BigInteger, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MarketDataCache(Base):
    __tablename__ = "market_data_cache"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Numeric(12, 4))
    close: Mapped[float] = mapped_column(Numeric(12, 4))
    high: Mapped[float] = mapped_column(Numeric(12, 4))
    low: Mapped[float] = mapped_column(Numeric(12, 4))
    volume: Mapped[int] = mapped_column(BigInteger)
    pe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    pb_ratio: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
