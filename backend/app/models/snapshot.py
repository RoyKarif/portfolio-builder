import uuid
from datetime import date

from sqlalchemy import Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"))
    date: Mapped[date] = mapped_column(Date)
    total_value: Mapped[float] = mapped_column(Numeric(14, 2))
    daily_return: Mapped[float] = mapped_column(Numeric(8, 4))

    portfolio = relationship("Portfolio", back_populates="snapshots")
