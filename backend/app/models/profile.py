import uuid
from sqlalchemy import String, Integer, Numeric, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvestmentProfile(Base):
    __tablename__ = "investment_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    risk_level: Mapped[int] = mapped_column(Integer)
    investment_horizon: Mapped[str] = mapped_column(String(20))
    available_amount: Mapped[float] = mapped_column(Numeric(14, 2))
    target_return: Mapped[float] = mapped_column(Numeric(5, 2))
    preferred_sectors: Mapped[list] = mapped_column(JSON, default=list)
    include_tickers: Mapped[list] = mapped_column(JSON, default=list)
    exclude_tickers: Mapped[list] = mapped_column(JSON, default=list)

    user = relationship("User", back_populates="profiles")
    portfolios = relationship("Portfolio", back_populates="profile")
