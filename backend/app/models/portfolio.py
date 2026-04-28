"""Portfolio ORM model — represents a row in the `portfolios` table.

A Portfolio is a snapshot of one "build" action: the user inputs
(amount, risk level, horizon, tickers) and the resulting outputs
(MVO weights, expected stats, Monte Carlo summary, RNG seed).

We store the seed so that re-loading the same portfolio later produces
the identical Monte Carlo fan chart — full reproducibility.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from sqlalchemy import String, DateTime, Integer, SmallInteger, Numeric, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Portfolio(Base):
    """One user-initiated portfolio build with its inputs and outputs."""

    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # FK to users.id with ON DELETE CASCADE: deleting a user removes
    # their portfolios automatically — clean account deletion.
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Display name. User can name it ("Aggressive 2026") or we generate
    # one ("Portfolio #3").
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )

    # --- Inputs (what the user requested) ---

    # Initial investment amount in dollars. NUMERIC(14,2) — up to
    # $999,999,999,999.99. We use NUMERIC, never FLOAT, for money.
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=14, scale=2),
        nullable=False,
    )

    # Risk level 1..5 chosen on the slider.
    # CheckConstraint adds DB-level validation — even a buggy app cannot
    # write 7 here.
    risk_level: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    horizon_years: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )

    # Volatility target (e.g. 0.12 = 12%) derived from risk_level via
    # RISK_LEVEL_TO_VOLATILITY. Stored explicitly so future changes to
    # the mapping don't retroactively alter old portfolios.
    target_volatility: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4),
        nullable=False,
    )

    # --- Outputs (what the engine computed) ---

    # Mapping {ticker: weight}, e.g. {"SPY": 0.45, "AGG": 0.30}.
    # JSONB (not JSON) — Postgres binary format, faster and indexable.
    # Chosen over a separate weights table because:
    #   1. We always read all weights together.
    #   2. Variable schema (each portfolio has different tickers).
    #   3. Saves a JOIN.
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Annualized expected return of the portfolio (e.g. 0.0825 = 8.25%).
    expected_return: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4),
        nullable=False,
    )

    expected_volatility: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4),
        nullable=False,
    )

    # (expected_return - risk_free) / expected_volatility
    sharpe_ratio: Mapped[Decimal] = mapped_column(
        Numeric(precision=6, scale=4),
        nullable=False,
    )

    # Monte Carlo summary: percentiles, VaR, and a per-year timeline
    # for the fan chart.
    # Example shape:
    #   {"p5": 8500, "p25": 11200, "p50": 14300, "p75": 18900,
    #    "p95": 27500, "var_5": -1500,
    #    "timeline": [{"year": 0, "p5": 10000, ...}, ...]}
    mc_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Random seed used by the Monte Carlo simulator. Stored so reloading
    # the portfolio reproduces the exact same fan chart.
    mc_seed: Mapped[int] = mapped_column(Integer, nullable=False)

    # Table-level constraints expressed as a tuple. Two CHECK constraints
    # ensure the DB rejects out-of-range values even if app code is buggy.
    __table_args__ = (
        CheckConstraint("risk_level BETWEEN 1 AND 5", name="ck_risk_level_range"),
        CheckConstraint("horizon_years BETWEEN 1 AND 30", name="ck_horizon_range"),
    )

    def __repr__(self) -> str:
        return f"<Portfolio id={self.id} user_id={self.user_id} name={self.name!r}>"
