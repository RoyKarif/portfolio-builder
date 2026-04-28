"""Asset ORM model — represents a row in the `assets` table.

An Asset is any ticker the system knows about — either one of the 20
curated ETFs (is_curated=True) or a custom ticker that some user added
via yfinance (is_curated=False).
"""

from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Asset(Base):
    """A tradeable instrument (ETF, stock) known to the system."""

    __tablename__ = "assets"

    # Ticker IS the primary key — no synthetic id. A ticker is naturally
    # unique, short, and stable enough. Saves a JOIN whenever we have a
    # ticker string and need its metadata.
    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)

    # Display name. Shown in the UI ("SPDR S&P 500 ETF" vs "SPY").
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # One of: equity, bond, commodity, real_estate, cash. Stored as a
    # plain string (not ENUM) so we can add new classes without a
    # migration. We CAN convert to a real ENUM later once the set is
    # stable.
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)

    # True for the 20 ETFs we seed; False for custom tickers added by users.
    # The /api/universe endpoint filters on this flag.
    is_curated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return f"<Asset {self.ticker} ({self.asset_class})>"
