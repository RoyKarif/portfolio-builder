"""Price ORM model — represents a row in the `prices` table.

The heart of the data layer. Each row is one (ticker, date, close)
triple. The MVO and Monte Carlo engines read from here to compute
μ and Σ.

Storage: ~25 ETFs × 2,500 trading days = ~62K rows. Tiny.
"""

from datetime import date as date_type
from decimal import Decimal
from sqlalchemy import String, Date, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Price(Base):
    """Daily adjusted-close price for one asset on one day."""

    __tablename__ = "prices"

    # Composite primary key: (ticker, date). A ticker can have many dates,
    # a date can have many tickers, but the pair is unique.
    # ForeignKey to assets.ticker enforces referential integrity:
    # you cannot insert a price for a ticker that doesn't exist in `assets`.
    # ON DELETE CASCADE: deleting an asset removes its prices automatically.
    ticker: Mapped[str] = mapped_column(
        String(10),
        ForeignKey("assets.ticker", ondelete="CASCADE"),
        primary_key=True,
    )

    date: Mapped[date_type] = mapped_column(Date, primary_key=True)

    # Adjusted close price (handles splits and dividends).
    # NUMERIC(12,4) — up to 12 digits total, 4 after the decimal.
    # NUMERIC (not FLOAT) avoids binary rounding surprises in money math.
    close: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=4),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Price {self.ticker} {self.date} {self.close}>"
