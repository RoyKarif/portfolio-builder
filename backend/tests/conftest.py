"""Shared pytest fixtures.

Tests run against an in-memory or test PostgreSQL DB (depending on the
DATABASE_URL env var when pytest runs). The fixtures here provide:

  - `db`: a SQLAlchemy session that's rolled back after each test
    (so tests don't leak state into each other).
  - `client`: a FastAPI TestClient backed by `db`.
  - `authenticated_client`: a client with a valid JWT for a test user.
  - `seeded_db`: db with synthetic asset+price data for engine tests.
"""

from datetime import date, timedelta
from decimal import Decimal
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app
from app.models import Asset, Price, User
from app.auth.password import hash_password
from app.auth.jwt import create_access_token


# Tests run against a separate test database. The TEST_DATABASE_URL env
# var lets CI inject a different connection string. Default points at a
# local Postgres instance ('postgres:test@localhost') configured in CI.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://portfolio:portfolio@db:5432/portfolio_builder_test",
)


@pytest.fixture(scope="session")
def engine():
    """One engine per test session. Tables created once, dropped at end."""
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)


@pytest.fixture
def db(engine):
    """Per-test session. Rolls back at teardown so tests are isolated."""
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionFactory()
    yield session
    session.rollback()
    # Brutal cleanup: delete every row in dependency order.
    # Faster than truncating tables because Postgres can use the indexes.
    session.execute(__import__("sqlalchemy").text("DELETE FROM portfolios"))
    session.execute(__import__("sqlalchemy").text("DELETE FROM prices"))
    session.execute(__import__("sqlalchemy").text("DELETE FROM assets"))
    session.execute(__import__("sqlalchemy").text("DELETE FROM users"))
    session.commit()
    session.close()


@pytest.fixture
def client(db):
    """TestClient that uses the test db via dependency override."""
    def _get_test_db():
        yield db

    app.dependency_overrides[get_db] = _get_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db) -> User:
    """A pre-created user for auth tests."""
    user = User(
        email="alice@example.com",
        password_hash=hash_password("Password123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def authenticated_client(client, test_user) -> TestClient:
    """TestClient with `Authorization: Bearer <token>` set for test_user."""
    token = create_access_token(test_user.id)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture
def seeded_db(db) -> None:
    """Populate db with eight synthetic assets and 1 year of fake prices.

    Prices are deterministic (seed=0) so engine tests are reproducible.

    Universe size = 8: large enough to satisfy the production MVO config,
    which uses max_single_weight=0.20 (forces ≥5 holdings) and asymmetric
    class caps (equity ≤70%, commodity ≤30%, bond/cash uncapped). The mix
    below — 5 equity + 2 bond + 1 cash — leaves enough non-equity to
    satisfy the equity cap, and enough holdings overall for the per-asset
    cap to be feasible.
    """
    rng = np.random.default_rng(0)
    assets = [
        ("AAA", "Equity A", "equity"),
        ("BBB", "Equity B", "equity"),
        ("CCC", "Equity C", "equity"),
        ("DDD", "Equity D", "equity"),
        ("EEE", "Equity E", "equity"),
        ("FFF", "Bond F",   "bond"),
        ("GGG", "Bond G",   "bond"),
        ("HHH", "Cash H",   "cash"),
    ]
    for ticker, name, asset_class in assets:
        db.add(Asset(
            ticker=ticker, name=name,
            asset_class=asset_class, is_curated=True,
        ))
    db.commit()

    # Per-ticker (drift, vol) — different enough that MVO has interesting
    # choices across risk levels but not so different that the optimizer
    # collapses onto a single asset.
    params = {
        "AAA": (0.0009, 0.013),
        "BBB": (0.0007, 0.012),
        "CCC": (0.0006, 0.011),
        "DDD": (0.0005, 0.010),
        "EEE": (0.0004, 0.009),
        "FFF": (0.0002, 0.004),
        "GGG": (0.0001, 0.003),
        "HHH": (0.00005, 0.001),
    }

    # Generate 252 weekday-only trading days ending today. Walking back
    # from today (instead of forward from a fixed start) is what keeps
    # the latest price date == today, which lets ensure_prices_fresh
    # treat the cache as fresh and skip the yfinance/synthetic re-fetch
    # — so tests run against fully deterministic seeded data.
    trading_days: list[date] = []
    d = date.today()
    while len(trading_days) < 252:
        if d.weekday() < 5:  # Mon-Fri only
            trading_days.append(d)
        d -= timedelta(days=1)
    trading_days.reverse()  # oldest first, so prices compound forward

    for ticker, (drift, vol) in params.items():
        price = 100.0
        for dt in trading_days:
            r = rng.normal(drift, vol)
            price = price * np.exp(r)
            db.add(Price(
                ticker=ticker,
                date=dt,
                close=Decimal(f"{price:.4f}"),
            ))
    db.commit()
